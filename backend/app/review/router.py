from datetime import timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import fsrs
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.grammar.catalog import PATTERNS, PatternKey
from app.grammar.service import add_evidence
from app.mistakes.models import Mistake
from app.review.grading import (
    article_evidence,
    check_article,
    check_correction,
    check_produce,
    produce_evidence,
    uses_word,
)
from app.review.models import CardType, ReviewCard, ReviewLog
from app.review.schemas import (
    QueueCard,
    QueueMistake,
    QueueOut,
    QueueWord,
    ReviewHistoryOut,
    ReviewIn,
    ReviewOut,
)
from app.review.service import (
    IS_SCHEDULED,
    IS_UNSTARTED,
    LEARN_AHEAD,
    NEW_CARD_ORDER,
    NEW_CARDS_PER_DAY,
    apply_rating,
    queue_counts,
    recompute_stage,
    sync_cards,
    utcnow,
)
from app.review.stages import STAGE_REASONS
from app.vocabulary.models import VocabWord

router = APIRouter(tags=["review"])

# Answers given offline are uploaded later with the time they were given. A time outside this
# range means the phone's clock is wrong, not that the answer is: it is then counted as given now.
# Refusing it would lose the answer, because the app can't do anything else with it.
MAX_OFFLINE_AGE = timedelta(days=60)
MAX_CLOCK_SKEW = timedelta(minutes=2)


def get_timezone(
    tz: Annotated[str, Query(max_length=64, description="IANA name, e.g. Asia/Karachi")] = "UTC",
) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown timezone") from exc


TimezoneDep = Annotated[ZoneInfo, Depends(get_timezone)]


@router.get("/reviews/queue")
async def review_queue(
    user: CurrentUserDep,
    session: SessionDep,
    tz: TimezoneDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> QueueOut:
    """Today's reviews: cards due now, then new cards within the daily limit."""
    await sync_cards(session, user.id)
    await session.commit()

    now = utcnow()
    horizon = now + LEARN_AHEAD
    counts = await queue_counts(session, user.id, now, tz)
    mine = ReviewCard.user_id == user.id

    base = (
        select(ReviewCard, VocabWord, Mistake)
        .outerjoin(VocabWord, VocabWord.id == ReviewCard.word_id)
        .outerjoin(Mistake, Mistake.id == ReviewCard.mistake_id)
        .where(mine)
    )
    due_rows = (
        await session.execute(
            base.where(IS_SCHEDULED, ReviewCard.due <= horizon)
            .order_by(ReviewCard.due)
            .limit(limit)
        )
    ).all()
    new_rank = case({t: i for i, t in enumerate(NEW_CARD_ORDER)}, value=ReviewCard.card_type)
    new_rows = (
        await session.execute(
            base.where(IS_UNSTARTED)
            .order_by(VocabWord.created_at, VocabWord.id, new_rank)
            .limit(min(counts.new_allowed, max(0, limit - len(due_rows))))
        )
    ).all()

    return QueueOut(
        cards=[
            QueueCard(
                card_id=card.id,
                card_type=card.card_type,
                is_new=card.reps == 0,
                due=card.due,
                word=QueueWord.model_validate(word) if word else None,
                mistake=_queue_mistake(mistake) if mistake else None,
            )
            for card, word, mistake in [*due_rows, *new_rows]
        ],
        due_count=counts.due,
        new_count=counts.new,
        new_per_day=NEW_CARDS_PER_DAY,
        next_due_at=counts.next_due_at,
    )


def _queue_mistake(m: Mistake) -> QueueMistake:
    return QueueMistake(
        id=m.id,
        wrong=m.wrong,
        correct=m.correct,
        category=m.category,
        pattern_key=m.pattern_key,
        pattern_title=PATTERNS[m.pattern_key].title if m.pattern_key else None,
        explanation=m.explanation,
    )


def _out(
    log: ReviewLog,
    card: ReviewCard,
    word: VocabWord | None,
    *,
    feedback: str | None = None,
    changed: bool = False,
    duplicate: bool = False,
) -> ReviewOut:
    return ReviewOut(
        review_id=log.id,
        duplicate=duplicate,
        correct=log.correct,
        checked=log.checked,
        rating=log.rating,
        expected=log.expected,
        feedback=feedback,
        due=card.due,
        word_id=log.word_id,
        mistake_id=log.mistake_id,
        stage=word.stage if word else None,
        stage_reason=STAGE_REASONS[word.stage] if word else None,
        stage_changed=changed,
    )


@router.post("/reviews")
async def submit_review(
    body: ReviewIn, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ReviewOut:
    """Records one answer, reschedules the card with FSRS and updates the word's stage."""
    # Lock the card so two uploads of answers for it are applied one after the other.
    card = await session.scalar(
        select(ReviewCard)
        .where(ReviewCard.id == body.card_id, ReviewCard.user_id == user.id)
        .with_for_update()
    )
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
    word = await session.get_one(VocabWord, card.word_id) if card.word_id else None
    mistake = await session.get_one(Mistake, card.mistake_id) if card.mistake_id else None

    existing = await session.get(ReviewLog, body.id)
    if existing is not None:
        if existing.user_id != user.id or existing.card_id != card.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Review id already used")
        return _out(existing, card, word, duplicate=True)

    now = utcnow()
    reviewed_at = body.reviewed_at or now
    if reviewed_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reviewed_at needs a timezone")
    if reviewed_at > now + MAX_CLOCK_SKEW or reviewed_at < now - MAX_OFFLINE_AGE:
        reviewed_at = now  # the phone's clock is wrong: keep the answer, use our time
    if card.last_review and reviewed_at < card.last_review:
        reviewed_at = card.last_review  # keep each card's history in order

    rating = fsrs.Rating(body.rating)
    answer = body.answer
    expected = feedback = given = None
    checked = True
    grammar: dict[PatternKey, bool] = {}
    if card.card_type == CardType.ERROR_RETRY:
        assert mistake is not None
        if not answer.text:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Write the corrected version"
            )
        grade = check_correction(mistake.correct, answer.text)
        correct, expected, feedback, given = (
            grade.correct,
            grade.expected,
            grade.feedback,
            answer.text,
        )
        if mistake.pattern_key:
            grammar = {mistake.pattern_key: correct}
    else:
        assert word is not None
        match card.card_type:
            case CardType.RECALL:
                checked, correct = False, rating != fsrs.Rating.Again
            case CardType.PRODUCE:
                if not answer.text:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Type your answer")
                grade = check_produce(word, answer.text)
                correct, expected, feedback, given = (
                    grade.correct,
                    grade.expected,
                    grade.feedback,
                    answer.text,
                )
                grammar = produce_evidence(word, answer.text)
            case CardType.ARTICLE:
                grade = check_article(word, answer.article, answer.plural)
                correct, expected, feedback = grade.correct, grade.expected, grade.feedback
                given = " · ".join(p for p in (answer.article, answer.plural) if p) or None
                grammar = article_evidence(word, answer.article, answer.plural)
            case CardType.SENTENCE:
                if not answer.text or not uses_word(word, answer.text):
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        f"Use '{word.german}' (or one of its forms) in your sentence",
                    )
                # Self-assessed until automatic sentence checking arrives (Phase 6).
                checked, correct, given = False, rating >= fsrs.Rating.Good, answer.text
    if checked and not correct:
        rating = fsrs.Rating.Again  # a wrong answer always comes back soon

    apply_rating(card, rating, reviewed_at, body.duration_ms)
    log = ReviewLog(
        id=body.id,
        user_id=user.id,
        card_id=card.id,
        word_id=card.word_id,
        mistake_id=card.mistake_id,
        card_type=card.card_type,
        rating=rating.value,
        correct=correct,
        checked=checked,
        answer=given,
        expected=expected,
        duration_ms=body.duration_ms,
        reviewed_at=reviewed_at,
    )
    session.add(log)
    await session.flush()
    add_evidence(session, user.id, grammar, reviewed_at, review_log_id=log.id)

    changed = False
    if word is not None:
        before = word.stage
        await recompute_stage(session, word, tz)
        await sync_cards(session, user.id, [word.id])  # unlocks the sentence card at Familiar
        changed = word.stage != before
    await session.commit()

    return _out(log, card, word, feedback=feedback, changed=changed)


@router.get("/words/{word_id}/reviews")
async def word_reviews(
    word_id: UUID, user: CurrentUserDep, session: SessionDep
) -> list[ReviewHistoryOut]:
    """Recent answers for one word, newest first (for the word page)."""
    logs = await session.scalars(
        select(ReviewLog)
        .where(ReviewLog.word_id == word_id, ReviewLog.user_id == user.id)
        .order_by(ReviewLog.reviewed_at.desc())
        .limit(50)
    )
    return [ReviewHistoryOut.model_validate(log) for log in logs]
