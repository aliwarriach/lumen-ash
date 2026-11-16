"""Gathers the learner's evidence and turns it into the dashboard and the daily plan.

Everything is worked out when requested, from rows the other features already keep: nothing is
scheduled and no extra state is stored.
"""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Date, cast, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.capture.models import ClassTask
from app.coach.models import CoachCheck, WritingTask
from app.coach.service import task_progress
from app.course.models import Chapter, ChapterResource, ResourceKind
from app.dashboard import plan as planner
from app.dashboard.plan import (
    ClassTaskInfo,
    ExamPick,
    GrammarPick,
    PlanInputs,
    ResourceInfo,
    ReviewInfo,
    TaskInfo,
    build_plan,
)
from app.dashboard.progress import assess, week_studied
from app.dashboard.schemas import (
    CardsOut,
    ChaptersOut,
    ClassTasksOut,
    CurrentChapterOut,
    DashboardOut,
    GrammarOut,
    MistakesOut,
    NextExamOut,
    OnTrackOut,
    PlanItemOut,
    PlanOut,
    RecentMistakeOut,
    StageCount,
    TestStatusOut,
    VocabularyOut,
    WeakPatternBrief,
    WeakWordOut,
)
from app.exams import service as exam_service
from app.exams.revision import revision_plan, why_chapter
from app.exams.schemas import ChapterRef
from app.grammar.catalog import PATTERNS, PatternKey
from app.grammar.models import GrammarChapterLink, GrammarEvidence
from app.grammar.service import MIN_ATTEMPTS, pattern_stats, weak_patterns
from app.mistakes.models import Mistake
from app.review import service as review_service
from app.review.models import ReviewLog
from app.sentences.models import SentenceResult
from app.vocabulary.forms import WordKind
from app.vocabulary.models import VocabWord, WordStage

HISTORY_DAYS = 400  # how far back a streak can reach
WEAK_WINDOW = timedelta(days=30)
MAX_WEAK = 3
SPEAKING_WORDS = 5

NO_TEST_MESSAGE = "No test coming up. Add a test date to see a countdown and how ready you are."
REVISION_DONE_CARDS = 5  # reviewing this many cards from the revision chapter ticks the item


async def study_days(
    session: AsyncSession, user_id: UUID, tz: ZoneInfo, now: datetime
) -> set[date]:
    """The learner's local dates with any study: a review answer, checked writing, a chapter
    resource marked done, a grammar practice answer or a finished sentence lesson."""
    since = now - timedelta(days=HISTORY_DAYS)

    def day(
        column: InstrumentedAttribute[datetime] | InstrumentedAttribute[datetime | None],
    ) -> ColumnElement[date]:
        return cast(func.timezone(tz.key, column), Date)

    rows = await session.scalars(
        union(
            select(day(ReviewLog.reviewed_at)).where(
                ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= since
            ),
            select(day(CoachCheck.created_at)).where(
                CoachCheck.user_id == user_id, CoachCheck.created_at >= since
            ),
            select(day(ChapterResource.completed_at)).where(
                ChapterResource.user_id == user_id, ChapterResource.completed_at >= since
            ),
            select(day(GrammarEvidence.occurred_at)).where(
                GrammarEvidence.user_id == user_id,
                GrammarEvidence.exercise_id.is_not(None),
                GrammarEvidence.occurred_at >= since,
            ),
            select(day(SentenceResult.updated_at)).where(
                SentenceResult.user_id == user_id, SentenceResult.updated_at >= since
            ),
        )
    )
    return set(rows)


# --- Chapters ---


async def _chapters(session: AsyncSession, user_id: UUID) -> tuple[ChaptersOut, int | None]:
    rows = (
        await session.execute(
            select(
                Chapter,
                func.count(ChapterResource.id),
                func.count(ChapterResource.completed_at),
            )
            .outerjoin(ChapterResource, ChapterResource.chapter_id == Chapter.id)
            .where(Chapter.user_id == user_id)
            .group_by(Chapter.id)
            .order_by(Chapter.number)
        )
    ).all()
    completed = [c for c, total, done in rows if total and done == total]
    started = [(c, total, done) for c, total, done in rows if done]

    current = None
    if rows:
        # The furthest chapter with any progress; the next one if that is finished.
        if started:
            current = started[-1]
            if current[1] == current[2]:
                later = [r for r in rows if r[0].number > current[0].number]
                current = later[0] if later else current
        else:
            current = rows[0]
    out = ChaptersOut(
        total=len(rows),
        completed=len(completed),
        resources_total=sum(total for _, total, _ in rows),
        resources_done=sum(done for _, _, done in rows),
        current=CurrentChapterOut(
            id=current[0].id,
            number=current[0].number,
            title=current[0].title,
            resources_total=current[1],
            resources_done=current[2],
        )
        if current
        else None,
    )
    return out, current[0].number if current else None


async def _resources(
    session: AsyncSession,
    user_id: UUID,
    kind: ResourceKind,
    current_number: int | None,
    day_start: datetime,
) -> tuple[list[ResourceInfo], list[ResourceInfo]]:
    """(pending, done today) resources of one kind, in chapters up to the current one. Pending
    ones nearest the current chapter come first."""
    if current_number is None:
        return [], []
    rows = await session.execute(
        select(ChapterResource, Chapter.number)
        .join(Chapter, Chapter.id == ChapterResource.chapter_id)
        .where(
            ChapterResource.user_id == user_id,
            ChapterResource.kind == kind,
            Chapter.number <= current_number,
        )
        .order_by(Chapter.number.desc(), ChapterResource.position)
    )
    pending, done_today = [], []
    for r, number in rows:
        info = ResourceInfo(r.id, r.chapter_id, number, r.title, r.reference, r.url)
        if r.completed_at is None:
            pending.append(info)
        elif r.completed_at >= day_start:
            done_today.append(info)
    # Homework: oldest first, so nothing is left behind. Audio: nearest the current chapter.
    if kind == ResourceKind.WORKBOOK_EXERCISE:
        pending.sort(key=lambda r: r.chapter_number)
    return pending, done_today


# --- Words ---


def _display(word: VocabWord) -> str:
    if word.kind == WordKind.NOUN and word.article:
        return f"{word.article.value} {word.german}"
    return word.german


async def _weak_words(session: AsyncSession, user_id: UUID, now: datetime) -> list[WeakWordOut]:
    wrong = func.count().filter(ReviewLog.correct.is_(False))
    attempts = func.count()
    rows = await session.execute(
        select(ReviewLog.word_id, wrong, attempts)
        .where(
            ReviewLog.user_id == user_id,
            ReviewLog.checked.is_(True),
            ReviewLog.word_id.is_not(None),
            ReviewLog.reviewed_at >= now - WEAK_WINDOW,
        )
        .group_by(ReviewLog.word_id)
        .having(wrong > 0)
        .order_by(wrong.desc(), (wrong * 1.0 / attempts).desc(), ReviewLog.word_id)
        .limit(SPEAKING_WORDS)
    )
    found = rows.all()
    words = {
        w.id: w
        for w in await session.scalars(
            select(VocabWord).where(VocabWord.id.in_([r[0] for r in found]))
        )
    }
    return [
        WeakWordOut(
            id=word_id,
            german=words[word_id].german,
            article=words[word_id].article,
            wrong=n_wrong,
            attempts=n_attempts,
            reason=f"{n_wrong} wrong out of {n_attempts} checked answers in the last 30 days.",
        )
        for word_id, n_wrong, n_attempts in found
        if word_id in words
    ]


# --- Grammar ---


async def _grammar_pick(
    session: AsyncSession,
    user_id: UUID,
    weak: list[WeakPatternBrief],
    stats_attempts: dict[PatternKey, int],
    current_chapter_id: UUID | None,
    day_start: datetime,
) -> GrammarPick | None:
    pick: tuple[PatternKey, str, str] | None = None
    if weak:
        pick = (weak[0].key, weak[0].title, weak[0].reason)
    elif current_chapter_id is not None:
        # Nothing is going wrong yet: practise the pattern of this chapter we know least about.
        linked = list(
            await session.scalars(
                select(GrammarChapterLink.pattern_key).where(
                    GrammarChapterLink.user_id == user_id,
                    GrammarChapterLink.chapter_id == current_chapter_id,
                )
            )
        )
        thin = sorted(
            (k for k in linked if stats_attempts[k] < MIN_ATTEMPTS),
            key=lambda k: (stats_attempts[k], k),
        )
        if thin:
            n = stats_attempts[thin[0]]
            reason = (
                "In this chapter, and you haven't answered anything about it in 30 days."
                if n == 0
                else f"In this chapter, with only {n} checked answer{'s' if n != 1 else ''} "
                "in 30 days."
            )
            pick = (thin[0], PATTERNS[thin[0]].title, reason)
    if pick is None:
        return None
    key, title, reason = pick
    practised = await session.scalar(
        select(func.count()).where(
            GrammarEvidence.user_id == user_id,
            GrammarEvidence.pattern_key == key,
            GrammarEvidence.occurred_at >= day_start,
        )
    )
    return GrammarPick(key, title, reason, practised_today=bool(practised))


# --- Class tasks ---


async def _class_tasks(
    session: AsyncSession, user_id: UUID, today: date, day_start: datetime
) -> tuple[list[ClassTaskInfo], ClassTasksOut]:
    """(plan inputs, summary) for the tasks saved from the class chat."""
    rows = await session.scalars(
        select(ClassTask).where(
            ClassTask.user_id == user_id,
            (ClassTask.done_at.is_(None)) | (ClassTask.done_at >= day_start),
        )
    )
    infos: list[ClassTaskInfo] = []
    open_n = overdue = soon = 0
    for t in rows:
        if t.done_at is not None:
            infos.append(ClassTaskInfo(t.id, t.title, 0, t.url, done_today=True))
            continue
        open_n += 1
        if t.due_date is None:
            continue
        days_left = (t.due_date - today).days
        overdue += days_left < 0
        soon += 0 <= days_left <= planner.CLASS_TASK_URGENT_DAYS
        infos.append(ClassTaskInfo(t.id, t.title, days_left, t.url))
    return infos, ClassTasksOut(open=open_n, overdue=overdue, due_soon=soon)


# --- The next test ---


async def _next_test(
    session: AsyncSession,
    user_id: UUID,
    now: datetime,
    tz: ZoneInfo,
    today: date,
    day_start: datetime,
) -> tuple[TestStatusOut, ExamPick | None]:
    exam = await exam_service.next_exam(session, user_id, today)
    if exam is None:
        return TestStatusOut(next=None, message=NO_TEST_MESSAGE), None

    readiness = await exam_service.readiness_for(session, user_id, exam, now, tz)
    days_left = (exam.exam_date - today).days
    test = TestStatusOut(
        next=NextExamOut(
            id=exam.id,
            kind=exam.kind,
            title=exam.title,
            exam_date=exam.exam_date,
            days_left=days_left,
            verdict=readiness.verdict,
            headline=readiness.headline,
            estimate=readiness.estimate,
            target_percent=exam.target_percent,
            scope_note=readiness.scope_note,
            focus=[ChapterRef(id=c.id, number=c.number, title=c.title) for c in readiness.focus],
        ),
        message=None,
    )

    revision = revision_plan(today, exam.exam_date, readiness.focus)
    if revision.today is None:
        return test, None
    chapter = revision.today.chapter
    reviewed = await session.scalar(
        select(func.count())
        .select_from(ReviewLog)
        .join(VocabWord, VocabWord.id == ReviewLog.word_id)
        .where(
            ReviewLog.user_id == user_id,
            VocabWord.chapter_id == chapter.id,
            ReviewLog.reviewed_at >= day_start,
        )
    )
    pick = ExamPick(
        exam_id=exam.id,
        title=exam.title,
        days_left=days_left,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        chapter_title=chapter.title,
        why=why_chapter(exam.title, days_left, chapter),
        minutes=revision.today.minutes,
        words=chapter.unsecure_words,
        done=(reviewed or 0) >= REVISION_DONE_CARDS,
    )
    return test, pick


# --- The dashboard ---


async def build_dashboard(
    session: AsyncSession, user_id: UUID, tz: ZoneInfo, now: datetime
) -> DashboardOut:
    # Same as opening the review queue: new words get their cards, so the counts are right.
    await review_service.sync_cards(session, user_id)
    await session.commit()

    today = now.astimezone(tz).date()
    day_start = review_service.start_of_local_day(now, tz)

    counts = await review_service.queue_counts(session, user_id, now, tz)
    reviewed_today = (
        await session.scalar(
            select(func.count()).where(
                ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= day_start
            )
        )
        or 0
    )
    days = await study_days(session, user_id, tz, now)
    progress = assess(days, today, counts.due)

    chapters, current_number = await _chapters(session, user_id)
    current_id = chapters.current.id if chapters.current else None
    homework, homework_done = await _resources(
        session, user_id, ResourceKind.WORKBOOK_EXERCISE, current_number, day_start
    )
    audio, audio_done = await _resources(
        session, user_id, ResourceKind.AUDIO, current_number, day_start
    )

    # Grammar
    stats = await pattern_stats(session, user_id, now)
    attempts = sum(s.attempts for s in stats.values())
    correct = sum(s.correct for s in stats.values())
    weak = [
        WeakPatternBrief(key=w.key, title=w.title, accuracy=w.stats.accuracy, reason=w.reason)
        for w in await weak_patterns(session, user_id, now, MAX_WEAK)
    ]
    grammar = GrammarOut(
        attempts=attempts,
        correct=correct,
        accuracy=round(correct / attempts, 3) if attempts else None,
        weak=weak,
    )
    pick = await _grammar_pick(
        session, user_id, weak, {k: s.attempts for k, s in stats.items()}, current_id, day_start
    )

    # Words
    weak_words = await _weak_words(session, user_id, now)
    speaking = [f"{w.article.value} {w.german}" if w.article else w.german for w in weak_words]
    if not speaking:
        newest = await session.scalars(
            select(VocabWord)
            .where(VocabWord.user_id == user_id)
            .order_by(VocabWord.created_at.desc())
            .limit(SPEAKING_WORDS)
        )
        speaking = [_display(w) for w in newest]
    stage_rows = (
        await session.execute(
            select(VocabWord.stage, func.count())
            .where(VocabWord.user_id == user_id)
            .group_by(VocabWord.stage)
        )
    ).all()
    by_stage = {stage: n for stage, n in stage_rows}
    vocabulary = VocabularyOut(
        total=sum(by_stage.values()),
        mastered=by_stage.get(WordStage.MASTERED, 0),
        by_stage=[StageCount(stage=s, count=by_stage.get(s, 0)) for s in WordStage],
    )

    # Writing
    tasks = list(
        await session.scalars(
            select(WritingTask)
            .where(WritingTask.user_id == user_id)
            .order_by(WritingTask.created_at, WritingTask.id)
        )
    )
    progress_by_task = await task_progress(session, user_id, tasks)
    open_task = next((t for t in tasks if not progress_by_task[t.id][1]), None)
    sentences_today = (
        await session.scalar(
            select(func.coalesce(func.sum(CoachCheck.sentence_count), 0)).where(
                CoachCheck.user_id == user_id, CoachCheck.created_at >= day_start
            )
        )
        or 0
    )

    test, exam_pick = await _next_test(session, user_id, now, tz, today, day_start)
    class_task_infos, class_tasks = await _class_tasks(session, user_id, today, day_start)

    plan = build_plan(
        PlanInputs(
            review=ReviewInfo(counts.due, counts.new, counts.retries_due, reviewed_today),
            grammar=pick,
            homework_pending=homework,
            homework_done_today=homework_done,
            listening_pending=audio[0] if audio else None,
            listening_done_today=audio_done[0] if audio_done else None,
            current_chapter_number=current_number,
            speaking_words=speaking,
            speaking_words_are_weak=bool(weak_words),
            writing_task=TaskInfo(open_task.id, open_task.prompt, open_task.min_sentences)
            if open_task
            else None,
            sentences_today=int(sentences_today),
            exam=exam_pick,
            class_tasks=class_task_infos,
        )
    )

    # Mistakes
    recent_mistakes = list(
        await session.scalars(
            select(Mistake)
            .where(Mistake.user_id == user_id)
            .order_by(Mistake.created_at.desc(), Mistake.id)
            .limit(5)
        )
    )
    week_ago, month_ago = now - timedelta(days=7), now - timedelta(days=30)
    last_week = await session.scalar(
        select(func.count()).where(Mistake.user_id == user_id, Mistake.created_at >= week_ago)
    )
    repeats = await session.scalar(
        select(func.count()).where(
            Mistake.user_id == user_id,
            Mistake.created_at >= month_ago,
            Mistake.repeat_of_id.is_not(None),
        )
    )

    return DashboardOut(
        date=today,
        on_track=OnTrackOut(
            status=progress.status,
            reason=progress.reason,
            streak=progress.streak,
            days_studied=progress.days_studied,
            last_studied=progress.last_studied,
            week=week_studied(days, today),
        ),
        plan=PlanOut(
            items=[PlanItemOut.model_validate(i, from_attributes=True) for i in plan.items],
            total_minutes=plan.total_minutes,
            remaining_minutes=plan.remaining_minutes,
            note=plan.note,
        ),
        cards=CardsOut(due=counts.due, new=counts.new, reviewed_today=reviewed_today),
        vocabulary=vocabulary,
        chapters=chapters,
        grammar=grammar,
        weak_words=weak_words,
        mistakes=MistakesOut(
            last_7_days=last_week or 0,
            repeats_last_30_days=repeats or 0,
            recent=[
                RecentMistakeOut(
                    id=m.id,
                    wrong=m.wrong,
                    correct=m.correct,
                    pattern_title=PATTERNS[m.pattern_key].title if m.pattern_key else None,
                    created_at=m.created_at,
                )
                for m in recent_mistakes
            ],
        ),
        test=test,
        class_tasks=class_tasks,
    )


__all__ = ["build_dashboard", "planner"]
