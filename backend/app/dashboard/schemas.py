from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.types import UtcDatetime
from app.dashboard.plan import PlanKind
from app.dashboard.progress import TrackStatus
from app.exams.models import ExamKind
from app.exams.readiness import Verdict
from app.exams.schemas import ChapterRef
from app.grammar.catalog import PatternKey
from app.vocabulary.forms import Article
from app.vocabulary.models import WordStage


class OnTrackOut(BaseModel):
    status: TrackStatus
    reason: str = Field(description="Why, in one sentence with the learner's own numbers")
    streak: int = Field(description="Days in a row, counting today if already studied")
    days_studied: int = Field(description="Of the last 7 days")
    last_studied: date | None
    week: list[date] = Field(description="Days studied this week, Monday to today, in order")


class PlanItemOut(BaseModel):
    id: str = Field(description="Stable through the day")
    kind: PlanKind
    title: str
    why: str
    minutes: int
    done: bool | None = Field(description="null = not tracked: the app lets the learner tick it")
    pattern_key: PatternKey | None
    chapter_id: UUID | None
    resource_id: UUID | None
    task_id: UUID | None
    class_task_id: UUID | None = Field(description="The class-chat task, for 'class_task' items")
    url: str | None
    words: list[str]


class PlanOut(BaseModel):
    items: list[PlanItemOut]
    total_minutes: int
    remaining_minutes: int = Field(description="Minutes in the items that aren't done yet")
    note: str | None


class CardsOut(BaseModel):
    due: int
    new: int
    reviewed_today: int


class StageCount(BaseModel):
    stage: WordStage
    count: int


class VocabularyOut(BaseModel):
    total: int
    mastered: int
    by_stage: list[StageCount]


class CurrentChapterOut(BaseModel):
    id: UUID
    number: int
    title: str
    resources_done: int
    resources_total: int


class ChaptersOut(BaseModel):
    total: int
    completed: int
    resources_total: int
    resources_done: int
    current: CurrentChapterOut | None


class WeakPatternBrief(BaseModel):
    key: PatternKey
    title: str
    accuracy: float | None
    reason: str


class GrammarOut(BaseModel):
    attempts: int = Field(description="Checked uses of any pattern in the last 30 days")
    correct: int
    accuracy: float | None
    weak: list[WeakPatternBrief] = Field(description="Weakest first")


class WeakWordOut(BaseModel):
    id: UUID
    german: str
    article: Article | None
    wrong: int
    attempts: int
    reason: str


class RecentMistakeOut(BaseModel):
    id: UUID
    wrong: str
    correct: str
    pattern_title: str | None
    created_at: UtcDatetime


class MistakesOut(BaseModel):
    last_7_days: int
    repeats_last_30_days: int
    recent: list[RecentMistakeOut]


class NextExamOut(BaseModel):
    id: UUID
    kind: ExamKind
    title: str
    exam_date: date
    days_left: int
    verdict: Verdict
    headline: str = Field(description="e.g. 'Not ready yet: focus on Chapters 4–6.'")
    estimate: float | None
    target_percent: int
    scope_note: str | None
    focus: list[ChapterRef] = Field(description="Chapters to work on, in course order")


class TestStatusOut(BaseModel):
    next: NextExamOut | None
    message: str | None = Field(description="Set when there is no upcoming test")


class ClassTasksOut(BaseModel):
    """Tasks the learner saved from the class chat (Phase 9)."""

    open: int
    overdue: int
    due_soon: int = Field(description="Open and due within the next 2 days, not counting overdue")


class DashboardOut(BaseModel):
    """Answers the four questions: on track? what today? where weak? ready for the test?"""

    date: date
    on_track: OnTrackOut
    plan: PlanOut
    cards: CardsOut
    vocabulary: VocabularyOut
    chapters: ChaptersOut
    grammar: GrammarOut
    weak_words: list[WeakWordOut]
    mistakes: MistakesOut
    test: TestStatusOut
    class_tasks: ClassTasksOut
