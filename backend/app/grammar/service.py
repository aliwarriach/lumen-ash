"""Grammar accuracy, worked out from evidence rows when requested. Every number here should be
explainable to the learner in one sentence ("4 wrong out of 10 in the last 30 days")."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.grammar.catalog import PATTERNS, PatternKey
from app.grammar.exercises import BY_ID
from app.grammar.models import GrammarEvidence
from app.grammar.schemas import (
    EvidenceOut,
    EvidenceSource,
    PatternLevel,
    PatternStatsOut,
    WeakPatternOut,
)
from app.mistakes.models import Mistake
from app.review.models import CardType, ReviewLog

WINDOW = timedelta(days=30)
WEAK_BELOW = 0.7
STRONG_FROM = 0.9
# Fewer attempts than this and the level stays "not enough data", whatever the accuracy.
MIN_ATTEMPTS = 3

_REVIEW_LABELS = {
    CardType.ARTICLE: "Article card",
    CardType.PRODUCE: "Typed the German",
    CardType.ERROR_RETRY: "Mistake retry",
}


def add_evidence(
    session: AsyncSession,
    user_id: UUID,
    results: Mapping[PatternKey, bool],
    occurred_at: datetime,
    *,
    mistake_id: UUID | None = None,
    review_log_id: UUID | None = None,
    exercise_id: str | None = None,
    given: str | None = None,
) -> None:
    for key, correct in results.items():
        session.add(
            GrammarEvidence(
                user_id=user_id,
                pattern_key=key,
                correct=correct,
                occurred_at=occurred_at,
                mistake_id=mistake_id,
                review_log_id=review_log_id,
                exercise_id=exercise_id,
                given=given,
            )
        )


@dataclass
class _Counts:
    attempts: int = 0
    correct: int = 0
    previous_attempts: int = 0
    previous_correct: int = 0
    mistakes: int = 0
    repeats: int = 0
    last_mistake_at: datetime | None = None


def _accuracy(correct: int, attempts: int) -> float | None:
    return round(correct / attempts, 3) if attempts else None


def _level(attempts: int, accuracy: float | None) -> PatternLevel:
    if accuracy is None or attempts < MIN_ATTEMPTS:
        return PatternLevel.NOT_ENOUGH_DATA
    if accuracy < WEAK_BELOW:
        return PatternLevel.WEAK
    return PatternLevel.STRONG if accuracy >= STRONG_FROM else PatternLevel.OK


async def pattern_stats(
    session: AsyncSession, user_id: UUID, now: datetime
) -> dict[PatternKey, PatternStatsOut]:
    """Stats for every pattern in the catalogue, including ones never practised."""
    start, previous_start = now - WINDOW, now - 2 * WINDOW
    recent = GrammarEvidence.occurred_at >= start
    previous = and_(
        GrammarEvidence.occurred_at >= previous_start, GrammarEvidence.occurred_at < start
    )
    counts = {key: _Counts() for key in PATTERNS}

    evidence_rows = await session.execute(
        select(
            GrammarEvidence.pattern_key,
            func.count().filter(recent),
            func.count().filter(recent, GrammarEvidence.correct),
            func.count().filter(previous),
            func.count().filter(previous, GrammarEvidence.correct),
        )
        .where(GrammarEvidence.user_id == user_id, GrammarEvidence.occurred_at >= previous_start)
        .group_by(GrammarEvidence.pattern_key)
    )
    for key, attempts, correct, prev_attempts, prev_correct in evidence_rows:
        c = counts[key]
        c.attempts, c.correct = attempts, correct
        c.previous_attempts, c.previous_correct = prev_attempts, prev_correct

    mistake_rows = await session.execute(
        select(
            Mistake.pattern_key,
            func.count(),
            func.count(Mistake.repeat_of_id),
            func.max(Mistake.created_at),
        )
        .where(Mistake.user_id == user_id, Mistake.pattern_key.is_not(None))
        .group_by(Mistake.pattern_key)
    )
    for pattern, total, repeats, last_at in mistake_rows:
        assert pattern is not None
        c = counts[pattern]
        c.mistakes, c.repeats, c.last_mistake_at = total, repeats, last_at

    out = {}
    for key, c in counts.items():
        accuracy = _accuracy(c.correct, c.attempts)
        out[key] = PatternStatsOut(
            attempts=c.attempts,
            correct=c.correct,
            accuracy=accuracy,
            previous_accuracy=_accuracy(c.previous_correct, c.previous_attempts),
            level=_level(c.attempts, accuracy),
            mistakes=c.mistakes,
            repeats=c.repeats,
            last_mistake_at=c.last_mistake_at,
        )
    return out


def _evidence_query(user_id: UUID) -> Select[GrammarEvidence, Mistake, ReviewLog]:
    return (
        select(GrammarEvidence, Mistake, ReviewLog)
        .outerjoin(Mistake, Mistake.id == GrammarEvidence.mistake_id)
        .outerjoin(ReviewLog, ReviewLog.id == GrammarEvidence.review_log_id)
        .where(GrammarEvidence.user_id == user_id)
        .order_by(GrammarEvidence.occurred_at.desc(), GrammarEvidence.created_at.desc())
    )


def _evidence_out(e: GrammarEvidence, m: Mistake | None, log: ReviewLog | None) -> EvidenceOut:
    if m is not None:
        return EvidenceOut(
            pattern_key=e.pattern_key,
            correct=e.correct,
            occurred_at=e.occurred_at,
            source=EvidenceSource.MISTAKE,
            label="Logged mistake",
            given=m.wrong,
            expected=m.correct,
            mistake_id=m.id,
            word_id=None,
        )
    if e.exercise_id is not None:
        found = BY_ID.get(e.exercise_id)
        return EvidenceOut(
            pattern_key=e.pattern_key,
            correct=e.correct,
            occurred_at=e.occurred_at,
            source=EvidenceSource.PRACTICE,
            label="Practice",
            given=e.given,
            expected=found[1].answers[0] if found else None,
            mistake_id=None,
            word_id=None,
        )
    assert log is not None
    return EvidenceOut(
        pattern_key=e.pattern_key,
        correct=e.correct,
        occurred_at=e.occurred_at,
        source=EvidenceSource.REVIEW,
        label=_REVIEW_LABELS.get(log.card_type, "Review"),
        given=log.answer,
        expected=log.expected,
        mistake_id=log.mistake_id,
        word_id=log.word_id,
    )


async def recent_evidence(
    session: AsyncSession,
    user_id: UUID,
    key: PatternKey,
    *,
    limit: int = 20,
    wrong_only: bool = False,
) -> list[EvidenceOut]:
    query = _evidence_query(user_id).where(GrammarEvidence.pattern_key == key).limit(limit)
    if wrong_only:
        query = query.where(GrammarEvidence.correct.is_(False))
    return [_evidence_out(e, m, log) for e, m, log in await session.execute(query)]


def _weakness(stats: PatternStatsOut) -> float:
    # Accuracy pulled towards 75% by four imagined attempts, so a pattern needs a few answers
    # before it ranks as the weakest: one slip out of one isn't worse than 2 wrong out of 3,
    # and 90 right out of 100 stays well clear of either. Lower is weaker.
    return (stats.correct + 3) / (stats.attempts + 4)


def weak_reason(stats: PatternStatsOut) -> str:
    wrong = stats.attempts - stats.correct
    reason = f"{wrong} wrong out of {stats.attempts} in the last 30 days"
    if stats.accuracy is not None:
        reason += f" ({round(stats.accuracy * 100)}% right)"
    if stats.previous_accuracy is not None and stats.accuracy is not None:
        before, now = round(stats.previous_accuracy * 100), round(stats.accuracy * 100)
        if now != before:
            reason += f", {'up' if now > before else 'down'} from {before}%"
    if stats.repeats:
        reason += f". {stats.repeats} repeated mistake{'s' if stats.repeats != 1 else ''}"
    return reason + "."


async def weak_patterns(
    session: AsyncSession, user_id: UUID, now: datetime, limit: int
) -> list[WeakPatternOut]:
    """Patterns with at least one wrong answer in the last 30 days, weakest first."""
    stats = await pattern_stats(session, user_id, now)
    weak = [(k, s) for k, s in stats.items() if s.attempts > s.correct]
    weak.sort(key=lambda ks: (_weakness(ks[1]), -(ks[1].attempts - ks[1].correct), ks[0]))
    return [
        WeakPatternOut(
            key=key,
            title=PATTERNS[key].title,
            category=PATTERNS[key].category,
            stats=s,
            reason=weak_reason(s),
            evidence=await recent_evidence(session, user_id, key, limit=3, wrong_only=True),
        )
        for key, s in weak[:limit]
    ]
