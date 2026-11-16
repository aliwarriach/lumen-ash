"""The daily plan, built from data. Pure functions: everything the plan needs is passed in.

Rules (see docs/build-history.md, Phase 7):
- Items are in priority order: due reviews, class tasks due within two days (or overdue), one
  weak grammar pattern, pending homework, class tasks due within a week, writing, listening,
  speaking. Revising for an approaching test comes after the grammar item, or right after reviews
  in the last three days. Class tasks are what the learner approved from the class chat (Phase 9);
  one with no date never enters the plan, it only shows in the task list.
- Every item says *why* it is there, with the learner's own numbers.
- The plan adds up to at most 60 minutes. Items that don't fit are named, not silently dropped.
- Items the learner has already done today stay in the list, ticked, so progress is visible.
- Listening and speaking aren't tracked yet, so unless a listening item is a chapter audio
  resource (done when the learner marks it complete) its `done` is None, and the app lets the
  learner tick it off on the phone.
"""

import math
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.grammar.catalog import PatternKey

MAX_MINUTES = 60
TARGET_MINUTES = 30  # below this the plan says it's a light day
SECONDS_PER_CARD = 24
REVIEW_MINUTES = (5, 20)  # shortest and longest review block
GRAMMAR_MINUTES = 5
HOMEWORK_MINUTES = 10
MAX_HOMEWORK_ITEMS = 2
EXAM_SOON_DAYS = 3  # this close, revision goes ahead of the grammar item
WRITING_MINUTES = 10
LISTENING_MINUTES = 8
SPEAKING_MINUTES = 5
FREE_WRITING_SENTENCES = 5
CLASS_TASK_MINUTES = 10
CLASS_TASK_URGENT_DAYS = 2  # due this soon (or overdue): ahead of grammar
CLASS_TASK_HORIZON_DAYS = 7  # further out than this stays off the plan
MAX_URGENT_CLASS_TASKS = 3
MAX_LATER_CLASS_TASKS = 2


class PlanKind(StrEnum):
    REVIEW = "review"
    GRAMMAR = "grammar"
    HOMEWORK = "homework"
    CLASS_TASK = "class_task"
    WRITING = "writing"
    LISTENING = "listening"
    SPEAKING = "speaking"
    EXAM = "exam"


@dataclass(frozen=True)
class ReviewInfo:
    due: int
    new: int
    retries_due: int
    reviewed_today: int


@dataclass(frozen=True)
class GrammarPick:
    key: PatternKey
    title: str
    reason: str
    practised_today: bool


@dataclass(frozen=True)
class ResourceInfo:
    id: UUID
    chapter_id: UUID
    chapter_number: int
    title: str
    reference: str | None
    url: str | None


@dataclass(frozen=True)
class TaskInfo:
    id: UUID
    prompt: str
    min_sentences: int


@dataclass(frozen=True)
class ClassTaskInfo:
    """A task the learner approved from the class chat."""

    id: UUID
    title: str
    days_left: int  # negative when overdue
    url: str | None
    done_today: bool = False


@dataclass(frozen=True)
class ExamPick:
    """Today's revision chapter for the next test (see exams/revision.py)."""

    exam_id: UUID
    title: str
    days_left: int
    chapter_id: UUID
    chapter_number: int
    chapter_title: str
    why: str
    minutes: int
    words: list[str]
    done: bool


@dataclass(frozen=True)
class PlanInputs:
    review: ReviewInfo
    grammar: GrammarPick | None = None
    homework_pending: list[ResourceInfo] = field(default_factory=list)
    homework_done_today: list[ResourceInfo] = field(default_factory=list)
    listening_pending: ResourceInfo | None = None
    listening_done_today: ResourceInfo | None = None
    current_chapter_number: int | None = None
    speaking_words: list[str] = field(default_factory=list)
    speaking_words_are_weak: bool = False
    writing_task: TaskInfo | None = None  # the oldest task that isn't done yet
    sentences_today: int = 0
    exam: ExamPick | None = None
    # Open tasks with a date, and tasks ticked off today. Any order.
    class_tasks: list[ClassTaskInfo] = field(default_factory=list)


@dataclass
class PlanItem:
    id: str  # stable through the day, so the app can remember a manual tick
    kind: PlanKind
    title: str
    why: str
    minutes: int
    done: bool | None
    pattern_key: PatternKey | None = None
    chapter_id: UUID | None = None
    resource_id: UUID | None = None
    task_id: UUID | None = None
    class_task_id: UUID | None = None
    url: str | None = None
    words: list[str] = field(default_factory=list)


@dataclass
class Plan:
    items: list[PlanItem]
    total_minutes: int
    remaining_minutes: int
    note: str | None


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _review_item(r: ReviewInfo) -> PlanItem | None:
    cards = r.due + r.new
    if cards == 0 and r.reviewed_today == 0:
        return None
    low, high = REVIEW_MINUTES
    minutes = min(high, max(low, math.ceil(cards * SECONDS_PER_CARD / 60)))
    if cards == 0:
        title, why = "Reviews", f"All done: you reviewed {_plural(r.reviewed_today, 'card')} today."
    else:
        title = f"Review {_plural(cards, 'card')}"
        parts = []
        if r.due:
            due = f"{_plural(r.due, 'card')} due"
            parts.append(
                due + (f", {r.retries_due} of them mistake retries" if r.retries_due else "")
            )
        if r.new:
            parts.append(f"{r.new} new" if r.due else f"{_plural(r.new, 'new card')} to start")
        why = " and ".join(parts) + "."
    return PlanItem("review", PlanKind.REVIEW, title, why, minutes, done=cards == 0)


def _grammar_item(g: GrammarPick) -> PlanItem:
    return PlanItem(
        f"grammar:{g.key.value}",
        PlanKind.GRAMMAR,
        f"Practise: {g.title}",
        g.reason,
        GRAMMAR_MINUTES,
        done=g.practised_today,
        pattern_key=g.key,
    )


def _homework_item(r: ResourceInfo, done: bool) -> PlanItem:
    where = f" ({r.reference})" if r.reference else ""
    why = (
        f"Chapter {r.chapter_number} workbook exercise, marked done today."
        if done
        else f"Chapter {r.chapter_number} workbook exercise you haven't marked done yet."
    )
    return PlanItem(
        f"homework:{r.id}",
        PlanKind.HOMEWORK,
        f"Workbook: {r.title}{where}",
        why,
        HOMEWORK_MINUTES,
        done=done,
        chapter_id=r.chapter_id,
        resource_id=r.id,
        url=r.url,
    )


def _due_phrase(days_left: int) -> str:
    if days_left < -1:
        return f"{-days_left} days overdue"
    return {-1: "due yesterday", 0: "due today", 1: "due tomorrow"}.get(
        days_left, f"due in {days_left} days"
    )


def _class_task_item(t: ClassTaskInfo) -> PlanItem:
    why = (
        "From your class chat, ticked off today."
        if t.done_today
        else f"From your class chat: {_due_phrase(t.days_left)}."
    )
    return PlanItem(
        f"class_task:{t.id}",
        PlanKind.CLASS_TASK,
        t.title,
        why,
        CLASS_TASK_MINUTES,
        done=t.done_today,
        class_task_id=t.id,
        url=t.url,
    )


def _class_task_items(tasks: list[ClassTaskInfo]) -> tuple[list[PlanItem], list[PlanItem]]:
    """(urgent, later) plan items. Done-today ones stay beside their group so progress shows."""
    open_tasks = sorted((t for t in tasks if not t.done_today), key=lambda t: (t.days_left, t.id))
    urgent = [t for t in open_tasks if t.days_left <= CLASS_TASK_URGENT_DAYS]
    later = [
        t for t in open_tasks if CLASS_TASK_URGENT_DAYS < t.days_left <= CLASS_TASK_HORIZON_DAYS
    ]
    done = [t for t in tasks if t.done_today]
    return (
        [_class_task_item(t) for t in urgent[:MAX_URGENT_CLASS_TASKS]],
        [_class_task_item(t) for t in later[:MAX_LATER_CLASS_TASKS] + done],
    )


def _writing_item(i: PlanInputs) -> PlanItem:
    task = i.writing_task
    target = task.min_sentences if task else FREE_WRITING_SENTENCES
    done = i.sentences_today >= target
    if task:
        title = f"Write: {task.prompt}"
        why = f"Writing task: at least {_plural(target, 'sentence')}."
    else:
        title = f"Write {target} sentences"
        why = "Writing a few sentences a day is the quickest way to find your own mistakes."
    if i.sentences_today:
        why += f" You've checked {_plural(i.sentences_today, 'sentence')} today."
    return PlanItem(
        f"writing:{task.id}" if task else "writing",
        PlanKind.WRITING,
        title,
        why,
        WRITING_MINUTES,
        done=done,
        task_id=task.id if task else None,
    )


def _listening_item(i: PlanInputs) -> PlanItem:
    res = i.listening_done_today or i.listening_pending
    if res is not None:
        done = i.listening_done_today is not None
        where = f" ({res.reference})" if res.reference else ""
        return PlanItem(
            f"listening:{res.id}",
            PlanKind.LISTENING,
            f"Listen: {res.title}{where}",
            f"Chapter {res.chapter_number} audio, "
            + ("marked done today." if done else "not marked done yet."),
            LISTENING_MINUTES,
            done=done,
            chapter_id=res.chapter_id,
            resource_id=res.id,
            url=res.url,
        )
    where = (
        f"a dialogue from Chapter {i.current_chapter_number}"
        if i.current_chapter_number
        else "a short German dialogue"
    )
    return PlanItem(
        "listening",
        PlanKind.LISTENING,
        f"Listen to {where}",
        "Listening practice every day. Add the Allango audio to your chapter to see it here.",
        LISTENING_MINUTES,
        done=None,
    )


def _speaking_item(i: PlanInputs) -> PlanItem:
    if i.speaking_words:
        reason = (
            "Words you got wrong most recently."
            if i.speaking_words_are_weak
            else "Your newest words."
        )
        return PlanItem(
            "speaking",
            PlanKind.SPEAKING,
            f"Say these aloud: {', '.join(i.speaking_words)}",
            f"{reason} Speaking isn't tracked yet: tick it off yourself.",
            SPEAKING_MINUTES,
            done=None,
            words=i.speaking_words,
        )
    return PlanItem(
        "speaking",
        PlanKind.SPEAKING,
        "Speak German aloud for 5 minutes",
        "Introduce yourself or describe your day out loud. Speaking isn't tracked yet.",
        SPEAKING_MINUTES,
        done=None,
    )


def _exam_item(e: ExamPick) -> PlanItem:
    return PlanItem(
        f"exam:{e.exam_id}",
        PlanKind.EXAM,
        f"Revise Chapter {e.chapter_number}: {e.chapter_title}",
        e.why,
        e.minutes,
        done=e.done,
        chapter_id=e.chapter_id,
        words=e.words,
    )


def build_plan(i: PlanInputs) -> Plan:
    # Highest priority first. An item that doesn't fit in the hour is skipped, and named below.
    candidates: list[PlanItem] = []
    if review := _review_item(i.review):
        candidates.append(review)
    urgent_tasks, later_tasks = _class_task_items(i.class_tasks)
    candidates += urgent_tasks
    exam = _exam_item(i.exam) if i.exam else None
    close = i.exam is not None and i.exam.days_left <= EXAM_SOON_DAYS
    if exam and close:
        candidates.append(exam)
    if i.grammar:
        candidates.append(_grammar_item(i.grammar))
    if exam and not close:
        candidates.append(exam)
    homework = [(r, False) for r in i.homework_pending[:MAX_HOMEWORK_ITEMS]]
    homework += [(r, True) for r in i.homework_done_today]
    candidates += [_homework_item(r, done) for r, done in homework]
    candidates += later_tasks
    candidates += [_writing_item(i), _listening_item(i), _speaking_item(i)]

    items: list[PlanItem] = []
    left_out: list[PlanItem] = []
    total = 0
    for item in candidates:
        if total + item.minutes <= MAX_MINUTES:
            items.append(item)
            total += item.minutes
        else:
            left_out.append(item)

    remaining = sum(item.minutes for item in items if not item.done)
    notes = []
    if left_out:
        names = ", ".join(item.kind.value for item in left_out)
        notes.append(f"Left for another day to keep it under an hour: {names}.")
    if total < TARGET_MINUTES:
        notes.append("A light day: everything that is pending is in the plan.")
    return Plan(items, total, remaining, " ".join(notes) or None)
