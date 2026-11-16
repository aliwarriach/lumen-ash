from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey
from app.grammar.models import GrammarEvidence
from app.grammar.service import add_evidence
from app.mistakes.models import Mistake, mistake_words
from app.mistakes.schemas import MistakeOut, MistakeWordOut, RepeatOfOut, RetryOut
from app.review import service as review_service
from app.review.grading import normalize
from app.review.models import CardType, ReviewCard, ReviewLog
from app.vocabulary.models import VocabWord


def match_key(text: str) -> str:
    return normalize(text).lower()


async def log_mistake(
    session: AsyncSession,
    user_id: UUID,
    *,
    wrong: str,
    correct: str,
    category: MistakeCategory,
    pattern_key: PatternKey | None = None,
    explanation: str | None = None,
    chapter_id: UUID | None = None,
    source: str | None = None,
    words: Sequence[VocabWord] = (),
) -> Mistake:
    """Adds a mistake to the log: checks it for repeats, gives it an error-retry card and records
    its grammar evidence. Doesn't commit. Callers check that the chapter and words are the
    learner's own first."""
    now = review_service.utcnow()
    mistake = Mistake(
        user_id=user_id,
        wrong=wrong,
        correct=correct,
        category=category,
        pattern_key=pattern_key,
        explanation=explanation,
        chapter_id=chapter_id,
        source=source,
        match_key=match_key(correct),
        words=list(words),
        created_at=now,
    )
    session.add(mistake)
    await session.flush()
    mistake.repeat_of_id = await find_repeat(session, mistake, new=True)
    session.add(
        review_service.new_card(user_id, None, CardType.ERROR_RETRY, now, mistake_id=mistake.id)
    )
    await sync_evidence(session, mistake)
    return mistake


async def find_repeat(session: AsyncSession, mistake: Mistake, *, new: bool) -> UUID | None:
    """The most recent earlier mistake this one repeats: the same correction, or the same grammar
    pattern with one of the same words."""
    conditions = [Mistake.match_key == mistake.match_key]
    word_ids = [w.id for w in mistake.words]
    if mistake.pattern_key and word_ids:
        sharing = select(mistake_words.c.mistake_id).where(mistake_words.c.word_id.in_(word_ids))
        conditions.append(and_(Mistake.pattern_key == mistake.pattern_key, Mistake.id.in_(sharing)))
    query = select(Mistake.id).where(
        Mistake.user_id == mistake.user_id, Mistake.id != mistake.id, or_(*conditions)
    )
    if not new:  # a new mistake is later than everything saved; an edited one only some
        query = query.where(Mistake.created_at < mistake.created_at)
    return await session.scalar(query.order_by(Mistake.created_at.desc()).limit(1))


async def sync_evidence(session: AsyncSession, mistake: Mistake) -> None:
    """Rebuilds this mistake's grammar evidence: the mistake itself (wrong) plus each retry."""
    retry_logs = select(ReviewLog.id).where(ReviewLog.mistake_id == mistake.id)
    await session.execute(
        delete(GrammarEvidence).where(
            or_(
                GrammarEvidence.mistake_id == mistake.id,
                GrammarEvidence.review_log_id.in_(retry_logs),
            )
        )
    )
    if mistake.pattern_key is None:
        return
    key = mistake.pattern_key
    add_evidence(session, mistake.user_id, {key: False}, mistake.created_at, mistake_id=mistake.id)
    for log in await session.scalars(select(ReviewLog).where(ReviewLog.mistake_id == mistake.id)):
        add_evidence(
            session, mistake.user_id, {key: log.correct}, log.reviewed_at, review_log_id=log.id
        )


def _repeat_reason(mistake: Mistake, earlier: Mistake) -> str:
    if earlier.match_key == mistake.match_key:
        return "Same correction as before."
    shared = sorted({w.german for w in mistake.words} & {w.german for w in earlier.words})
    title = PATTERNS[mistake.pattern_key].title if mistake.pattern_key else "the same rule"
    return f"{title} again, with {', '.join(shared) or 'the same word'}."


async def mistakes_out(session: AsyncSession, mistakes: Sequence[Mistake]) -> list[MistakeOut]:
    ids = [m.id for m in mistakes]
    earlier_ids = {m.repeat_of_id for m in mistakes if m.repeat_of_id}
    earlier = (
        {m.id: m for m in await session.scalars(select(Mistake).where(Mistake.id.in_(earlier_ids)))}
        if earlier_ids
        else {}
    )
    cards = {
        c.mistake_id: c
        for c in await session.scalars(select(ReviewCard).where(ReviewCard.mistake_id.in_(ids)))
    }
    latest_retries = await session.execute(
        select(ReviewLog.mistake_id, ReviewLog.correct)
        .where(ReviewLog.mistake_id.in_(ids))
        .ext(distinct_on(ReviewLog.mistake_id))
        .order_by(ReviewLog.mistake_id, ReviewLog.reviewed_at.desc(), ReviewLog.created_at.desc())
    )
    last_correct = {mistake_id: correct for mistake_id, correct in latest_retries}

    out = []
    for m in mistakes:
        before = earlier.get(m.repeat_of_id) if m.repeat_of_id else None
        card = cards.get(m.id)
        out.append(
            MistakeOut(
                id=m.id,
                wrong=m.wrong,
                correct=m.correct,
                category=m.category,
                pattern_key=m.pattern_key,
                pattern_title=PATTERNS[m.pattern_key].title if m.pattern_key else None,
                explanation=m.explanation,
                chapter_id=m.chapter_id,
                source=m.source,
                words=[
                    MistakeWordOut(id=w.id, kind=w.kind, german=w.german, article=w.article)
                    for w in m.words
                ],
                repeat_of=RepeatOfOut(
                    id=before.id,
                    wrong=before.wrong,
                    created_at=before.created_at,
                    reason=_repeat_reason(m, before),
                )
                if before
                else None,
                retry=RetryOut(due=card.due, retries=card.reps, last_correct=last_correct.get(m.id))
                if card
                else None,
                created_at=m.created_at,
            )
        )
    return out
