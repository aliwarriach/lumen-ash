from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

import fsrs
from fsrs.card import CardDict
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.review.models import CardType, ReviewCard, ReviewLog
from app.review.stages import CardEvidence, SentenceEvidence, compute_stage
from app.vocabulary.forms import WordKind
from app.vocabulary.models import VocabWord, WordStage

NEW_CARDS_PER_DAY = 15
# Cards due within this window are shown now, so a short learning step doesn't end a session.
LEARN_AHEAD = timedelta(minutes=20)
# New cards are introduced in this order for each word: recognise it before producing it.
NEW_CARD_ORDER = [CardType.RECALL, CardType.ARTICLE, CardType.PRODUCE, CardType.SENTENCE]
_SENTENCE_STAGES = {WordStage.FAMILIAR, WordStage.USABLE, WordStage.MASTERED}


@lru_cache
def get_scheduler() -> fsrs.Scheduler:
    # Fuzzing spreads reviews so cards learned together don't stay bunched; off in tests.
    return fsrs.Scheduler(enable_fuzzing=get_settings().environment != "test")


def utcnow() -> datetime:
    return datetime.now(UTC)


def start_of_local_day(now: datetime, tz: ZoneInfo) -> datetime:
    local = now.astimezone(tz)
    return datetime.combine(local.date(), time.min, tzinfo=tz).astimezone(UTC)


def applicable_types(word: VocabWord) -> set[CardType]:
    types = {CardType.RECALL, CardType.PRODUCE}
    if word.kind == WordKind.NOUN and (word.article or word.plural_only):
        types.add(CardType.ARTICLE)
    if word.stage in _SENTENCE_STAGES:
        types.add(CardType.SENTENCE)
    return types


def new_card(
    user_id: UUID,
    word_id: UUID | None,
    card_type: CardType,
    now: datetime,
    *,
    mistake_id: UUID | None = None,
) -> ReviewCard:
    card = fsrs.Card(card_id=0, due=now)  # card_id is unused by us; 0 avoids fsrs's id sleep
    return ReviewCard(
        user_id=user_id,
        word_id=word_id,
        mistake_id=mistake_id,
        card_type=card_type,
        fsrs=cast(dict[str, Any], card.to_dict()),
        due=now,
        state=card.state.value,
        stability=None,
        reps=0,
        lapses=0,
    )


async def sync_cards(
    session: AsyncSession, user_id: UUID, word_ids: list[UUID] | None = None
) -> None:
    """Creates missing cards and removes ones that no longer apply (e.g. a noun became a verb).

    Sentence cards are never removed once created: their history is mastery evidence.
    """
    words_query = select(VocabWord).where(VocabWord.user_id == user_id)
    cards_query = select(ReviewCard.word_id, ReviewCard.card_type, ReviewCard.id).where(
        ReviewCard.user_id == user_id
    )
    if word_ids is not None:
        words_query = words_query.where(VocabWord.id.in_(word_ids))
        cards_query = cards_query.where(ReviewCard.word_id.in_(word_ids))

    cards_query = cards_query.where(ReviewCard.word_id.is_not(None))

    existing: dict[UUID, dict[CardType, UUID]] = defaultdict(dict)
    for word_id, card_type, card_id in await session.execute(cards_query):
        assert word_id is not None
        existing[word_id][card_type] = card_id

    now = utcnow()
    stale: list[UUID] = []
    for word in await session.scalars(words_query):
        wanted = applicable_types(word)
        have = existing.get(word.id, {})
        for card_type in wanted - have.keys():
            session.add(new_card(user_id, word.id, card_type, now))
        stale += [cid for t, cid in have.items() if t not in wanted and t != CardType.SENTENCE]
    if stale:
        await session.execute(delete(ReviewCard).where(ReviewCard.id.in_(stale)))
    await session.flush()


# Mistake retries are scheduled like reviews from the start: they don't wait for the new-card
# allowance, because fixing mistakes is the point of the app.
IS_RETRY = ReviewCard.card_type == CardType.ERROR_RETRY
IS_SCHEDULED = or_(ReviewCard.reps > 0, IS_RETRY)
IS_UNSTARTED = and_(ReviewCard.reps == 0, ~IS_RETRY)


@dataclass(frozen=True)
class QueueCounts:
    due: int  # cards due now or within the learn-ahead window
    retries_due: int  # of those, mistake retries
    new_allowed: int  # new cards the learner may still start today
    new: int  # new cards that will actually be offered (allowance, capped by what exists)
    next_due_at: datetime | None


async def queue_counts(
    session: AsyncSession, user_id: UUID, now: datetime, tz: ZoneInfo
) -> QueueCounts:
    """The numbers behind the review queue. The Review tab and the dashboard both use this, so
    they can never disagree about how many cards are due."""
    horizon = now + LEARN_AHEAD
    mine = ReviewCard.user_id == user_id
    started = await new_cards_started_today(session, user_id, start_of_local_day(now, tz))
    new_allowed = max(0, NEW_CARDS_PER_DAY - started)

    due = await session.scalar(
        select(func.count()).where(mine, IS_SCHEDULED, ReviewCard.due <= horizon)
    )
    retries = await session.scalar(
        select(func.count()).where(mine, IS_RETRY, ReviewCard.due <= horizon)
    )
    total_new = await session.scalar(select(func.count()).where(mine, IS_UNSTARTED))
    next_due_at = await session.scalar(
        select(func.min(ReviewCard.due)).where(mine, IS_SCHEDULED, ReviewCard.due > horizon)
    )
    return QueueCounts(
        due=due or 0,
        retries_due=retries or 0,
        new_allowed=new_allowed,
        new=min(new_allowed, total_new or 0),
        next_due_at=next_due_at,
    )


async def new_cards_started_today(session: AsyncSession, user_id: UUID, day_start: datetime) -> int:
    first_reviews = (
        select(ReviewLog.card_id)
        # Mistake retries don't use up the new-word allowance: they're always shown.
        .where(ReviewLog.user_id == user_id, ReviewLog.card_type != CardType.ERROR_RETRY)
        .group_by(ReviewLog.card_id)
        .having(func.min(ReviewLog.reviewed_at) >= day_start)
        .subquery()
    )
    return await session.scalar(select(func.count()).select_from(first_reviews)) or 0


def apply_rating(
    card: ReviewCard, rating: fsrs.Rating, reviewed_at: datetime, duration_ms: int | None
) -> None:
    updated, _ = get_scheduler().review_card(
        fsrs.Card.from_dict(cast(CardDict, card.fsrs)), rating, reviewed_at, duration_ms
    )
    card.fsrs = cast(dict[str, Any], updated.to_dict())
    card.due = updated.due
    card.state = updated.state.value
    card.stability = updated.stability
    card.reps += 1
    if rating == fsrs.Rating.Again and card.last_review is not None:
        card.lapses += 1
    card.last_review = reviewed_at


async def recompute_stage(session: AsyncSession, word: VocabWord, tz: ZoneInfo) -> WordStage:
    cards = {
        c.card_type: c
        for c in await session.scalars(select(ReviewCard).where(ReviewCard.word_id == word.id))
    }
    logs = await session.scalars(
        select(ReviewLog).where(ReviewLog.word_id == word.id).order_by(ReviewLog.reviewed_at)
    )
    last_correct: dict[CardType, bool] = {}
    sentence_days: set[date] = set()
    for log in logs:
        last_correct[log.card_type] = log.correct
        if log.card_type == CardType.SENTENCE and log.correct:
            sentence_days.add(log.reviewed_at.astimezone(tz).date())

    evidence = {
        t: CardEvidence(
            state=c.state, stability=c.stability, reps=c.reps, last_correct=last_correct.get(t)
        )
        for t, c in cards.items()
    }
    sentence = (
        SentenceEvidence(sentence_days, last_correct.get(CardType.SENTENCE))
        if CardType.SENTENCE in cards
        else None
    )
    word.stage = compute_stage(evidence, sentence)
    return word.stage
