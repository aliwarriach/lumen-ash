"""Gathers the learner's numbers for the progress review. Every figure comes from their own
records; the words around them come from app/progress/review.py."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, and_, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.course.models import ChapterResource
from app.dashboard.progress import streak
from app.dashboard.service import _chapters, study_days
from app.grammar.catalog import PATTERNS
from app.grammar.exercises import BOOK_CHAPTER
from app.grammar.models import GrammarEvidence
from app.grammar.schemas import PatternLevel
from app.grammar.service import pattern_stats
from app.mistakes.models import Mistake
from app.progress import review
from app.progress.schemas import MetricOut, ProgressReviewOut, StepOut
from app.review import service as review_service
from app.review.models import ReviewLog
from app.sentences.content import LESSONS
from app.sentences.models import SentenceResult
from app.vocabulary.models import VocabWord, WordStage

COMPLETED_FROM = 0.8  # a sentence lesson counts as completed from 80% right in one round
MISTAKE_WINDOW = timedelta(days=30)
MAX_IN_PROGRESS_LESSONS = 2


def _local_start(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(), tz).astimezone(UTC)


def _metric(label: str, this: int, last: int) -> MetricOut:
    change, rising = review.change_text(this, last)
    return MetricOut(label=label, value=this, change=change, rising=rising)


async def _two_weeks(
    session: AsyncSession,
    column: InstrumentedAttribute[datetime] | InstrumentedAttribute[datetime | None],
    where: list[ColumnElement[bool]],
    this_start: datetime,
    last_start: datetime,
    extra: ColumnElement[bool] | InstrumentedAttribute[bool] | None = None,
) -> tuple[int, int, int]:
    """(this week, last week, this week where `extra`) counts of rows by a timestamp column."""
    this = column >= this_start
    last = and_(column >= last_start, column < this_start)
    matching = (
        func.count().filter(this, extra) if extra is not None else func.count().filter(false())
    )
    row = (
        await session.execute(
            select(func.count().filter(this), func.count().filter(last), matching).where(
                *where, column >= last_start
            )
        )
    ).one()
    return int(row[0]), int(row[1]), int(row[2])


async def build_review(
    session: AsyncSession, user_id: UUID, tz: ZoneInfo, now: datetime
) -> ProgressReviewOut:
    today = now.astimezone(tz).date()
    this_start = _local_start(today - timedelta(days=6), tz)
    last_start = _local_start(today - timedelta(days=13), tz)

    days = await study_days(session, user_id, tz, now)
    days_this = sum(1 for d in days if today - timedelta(days=6) <= d <= today)
    days_last = sum(1 for d in days if today - timedelta(days=13) <= d < today - timedelta(days=6))

    cards_this, cards_last, cards_right = await _two_weeks(
        session, ReviewLog.reviewed_at, [ReviewLog.user_id == user_id], this_start, last_start,
        ReviewLog.correct,
    )  # fmt: skip
    practice_this, practice_last, practice_right = await _two_weeks(
        session, GrammarEvidence.occurred_at,
        [GrammarEvidence.user_id == user_id, GrammarEvidence.exercise_id.is_not(None)],
        this_start, last_start, GrammarEvidence.correct,
    )  # fmt: skip
    words_this, words_last, _ = await _two_weeks(
        session, VocabWord.created_at, [VocabWord.user_id == user_id], this_start, last_start
    )
    done_this, done_last, _ = await _two_weeks(
        session, ChapterResource.completed_at, [ChapterResource.user_id == user_id],
        this_start, last_start,
    )  # fmt: skip

    stages = dict(
        (
            await session.execute(
                select(VocabWord.stage, func.count())
                .where(VocabWord.user_id == user_id)
                .group_by(VocabWord.stage)
            )
        ).all()
    )
    words_total = sum(stages.values())
    mastered = stages.get(WordStage.MASTERED, 0)
    learning = sum(
        stages.get(s, 0) for s in (WordStage.LEARNING, WordStage.FAMILIAR, WordStage.USABLE)
    )

    results = {
        r.lesson_id: r
        for r in await session.scalars(
            select(SentenceResult).where(SentenceResult.user_id == user_id)
        )
    }
    completed = [
        r for r in results.values() if r.total and r.best_right / r.total >= COMPLETED_FROM
    ]

    stats = await pattern_stats(session, user_id, now)
    strong = sum(1 for s in stats.values() if s.level is PatternLevel.STRONG)
    weak = sum(1 for s in stats.values() if s.level is PatternLevel.WEAK)
    practised = sum(1 for s in stats.values() if s.attempts > 0)
    mistakes = (
        await session.scalar(
            select(func.count()).where(
                Mistake.user_id == user_id, Mistake.created_at >= now - MISTAKE_WINDOW
            )
        )
        or 0
    )
    counts = await review_service.queue_counts(session, user_id, now, tz)
    chapters, _ = await _chapters(session, user_id)

    numbers = review.Numbers(
        studied_ever=bool(days) or words_total > 0,
        days_this_week=days_this,
        days_last_week=days_last,
        streak=streak(days, today),
        cards_this_week=cards_this,
        cards_last_week=cards_last,
        answers_this_week=cards_this + practice_this,
        right_this_week=cards_right + practice_right,
        words_total=words_total,
        words_added_this_week=words_this,
        words_mastered=mastered,
        lessons_completed=len(completed),
        rules_strong=strong,
        resources_done_this_week=done_this,
    )
    tone, headline, message = review.headline_and_message(numbers)

    # --- What is under way ---
    in_progress: list[StepOut] = []
    current = chapters.current
    if current and current.resources_total:
        in_progress.append(
            StepOut(
                title=f"Kapitel {current.number}: {current.title}",
                detail=f"{current.resources_done} of {current.resources_total} course items done",
                progress=current.resources_done / current.resources_total,
                link=f"/chapters/{current.id}",
            )
        )
    if learning:
        in_progress.append(
            StepOut(
                title="Words you're learning",
                detail=f"{learning} on the way, {mastered} mastered so far",
                progress=mastered / words_total if words_total else None,
                link="/words",
            )
        )
    for lesson in [x for x in LESSONS if x.id in results and results[x.id] not in completed][
        :MAX_IN_PROGRESS_LESSONS
    ]:
        r = results[lesson.id]
        in_progress.append(
            StepOut(
                title=f"Sentences: {lesson.title}",
                detail=f"Best so far: {r.best_right} of {r.total}. One more round?",
                progress=r.best_right / r.total if r.total else None,
                link=f"/sentences/{lesson.id}",
            )
        )
    if practised:
        in_progress.append(
            StepOut(
                title="Grammar rules",
                detail=f"{practised} of {len(PATTERNS)} practised, {strong} strong",
                progress=practised / len(PATTERNS),
                link="/grammar",
            )
        )

    # --- What is next ---
    to_do: list[StepOut] = []
    waiting = counts.due + counts.new
    if waiting:
        to_do.append(
            StepOut(
                title="Review cards",
                detail=f"{waiting} card{'s' if waiting != 1 else ''} waiting for you",
                progress=None,
                link="/review/session",
            )
        )
    next_lesson = next((x for x in LESSONS if x.id not in results), None)
    if next_lesson:
        to_do.append(
            StepOut(
                title="Next sentence lesson",
                detail=f"Kapitel {next_lesson.book_chapter}: {next_lesson.title}",
                progress=None,
                link=f"/sentences/{next_lesson.id}",
            )
        )
    untried = sorted(
        (key for key, s in stats.items() if s.attempts == 0), key=lambda k: BOOK_CHAPTER[k]
    )
    if untried:
        key = untried[0]
        to_do.append(
            StepOut(
                title="Next grammar rule",
                detail=f"Kapitel {BOOK_CHAPTER[key]}: {PATTERNS[key].title}",
                progress=None,
                link=f"/grammar/practice/{key.value}",
            )
        )
    if current and current.resources_total > current.resources_done:
        left = current.resources_total - current.resources_done
        to_do.append(
            StepOut(
                title="Course items left",
                detail=f"{left} in Kapitel {current.number}",
                progress=None,
                link=f"/chapters/{current.id}",
            )
        )

    # --- Areas to improve: constructive, and kept in the Mistake Log ---
    improve = None
    if weak or mistakes:
        parts = []
        if weak:
            parts.append(f"{weak} grammar rule{'s need' if weak != 1 else ' needs'} more practice")
        if mistakes:
            parts.append(f"you logged {mistakes} mistake{'s' if mistakes != 1 else ''} in 30 days")
        improve = StepOut(
            title="Areas to improve",
            detail=" and ".join(parts).capitalize()
            + ". Your Mistake Log keeps them, so you can turn each one into a strength.",
            progress=None,
            link="/mistakes",
        )

    return ProgressReviewOut(
        tone=tone,
        headline=headline,
        message=message,
        this_week=[
            _metric("Days studied", days_this, days_last),
            _metric("Cards reviewed", cards_this, cards_last),
            _metric("Grammar answers", practice_this, practice_last),
            _metric("Words saved", words_this, words_last),
            _metric("Course items done", done_this, done_last),
        ],
        achievements=review.achievements(numbers),
        in_progress=in_progress,
        to_do=to_do,
        improve=improve,
    )
