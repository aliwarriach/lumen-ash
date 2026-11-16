from datetime import date
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.types import UtcDatetime
from app.exams.models import DEFAULT_TARGET_PERCENT, ExamKind, ResultKind, Skill
from app.exams.readiness import Verdict
from app.exams.revision import Phase

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
ChapterIds = Annotated[list[UUID], Field(max_length=50)]
Percent = Annotated[int, Field(ge=1, le=100)]


class ChapterRef(BaseModel):
    id: UUID
    number: int
    title: str


# --- Tests ---


class ExamCreate(BaseModel):
    kind: ExamKind
    title: Title
    exam_date: date
    chapter_ids: ChapterIds = Field(
        default=[], description="The chapters it covers. Empty means the whole course."
    )
    target_percent: Percent = Field(default=DEFAULT_TARGET_PERCENT, description="Your goal")
    notes: Notes | None = None


class ExamUpdate(BaseModel):
    """Partial update. kind, title, exam_date and target_percent can't be set to null."""

    kind: ExamKind | None = None
    title: Title | None = None
    exam_date: date | None = None
    chapter_ids: ChapterIds | None = None
    target_percent: Percent | None = None
    notes: Notes | None = None


class ReadinessBrief(BaseModel):
    verdict: Verdict
    headline: str
    estimate: float | None


class ExamOut(BaseModel):
    id: UUID
    kind: ExamKind
    title: str
    exam_date: date
    days_left: int = Field(description="Negative once the test has passed")
    phase: Phase
    whole_course: bool
    chapters: list[ChapterRef]
    target_percent: int
    notes: str | None
    results_count: int
    readiness: ReadinessBrief | None = Field(description="Only for tests that haven't passed")


# --- Readiness ---


class PartOut(BaseModel):
    name: str
    score: float | None
    detail: str


class ChapterReadinessOut(BaseModel):
    id: UUID
    number: int
    title: str
    score: float | None = Field(description="0-100; null = no evidence yet")
    detail: str
    needs_work: bool
    parts: list[PartOut]
    unsecure_words: list[str] = Field(description="Words not yet usable, weakest first")
    weak_patterns: list[str]
    lost_marks_in: list[str] = Field(description="Tests where you said you lost marks here")


class SkillOut(BaseModel):
    skill: str
    score: float | None
    detail: str
    tracked: bool = Field(description="False: only from test sections you entered")


class ReadinessOut(BaseModel):
    verdict: Verdict
    headline: str
    target: int
    estimate: float | None = Field(description="0-100, a rough estimate: not a predicted mark")
    learning_score: float | None = Field(description="From your vocabulary, grammar and workbook")
    practice_score: float | None = Field(description="Average of recent practice tests")
    recent_score: float | None = Field(description="Your three most recent chapters with evidence")
    scope_note: str | None
    reasons: list[str]
    chapters_with_evidence: int
    chapters_total: int
    chapters: list[ChapterReadinessOut]
    focus_chapter_ids: list[UUID]
    skills: list[SkillOut]


class RevisionDayOut(BaseModel):
    day: date
    days_left: int
    chapter: ChapterRef
    minutes: int
    why: str
    words: list[str]


class RevisionOut(BaseModel):
    phase: Phase
    schedule: list[RevisionDayOut] = Field(description="Today first, up to the day before")


# --- Results ---


class SectionIn(BaseModel):
    skill: Skill
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)

    @model_validator(mode="after")
    def in_range(self) -> Self:
        if self.score > self.max_score:
            raise ValueError("A section score can't be more than its maximum")
        return self


class ResultCreate(BaseModel):
    exam_id: UUID | None = Field(default=None, description="The test this belongs to, if any")
    kind: ResultKind
    title: Title | None = Field(default=None, description="e.g. 'Goethe Modelltest 2'")
    taken_on: date
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    sections: Annotated[list[SectionIn], Field(max_length=6)] = []
    weak_chapter_ids: ChapterIds = Field(default=[], description="Chapters you lost marks on")
    notes: Notes | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.score > self.max_score:
            raise ValueError("The score can't be more than the maximum")
        skills = [s.skill for s in self.sections]
        if len(set(skills)) != len(skills):
            raise ValueError("Each skill can appear once")
        return self


class SectionOut(BaseModel):
    skill: Skill
    score: float
    max_score: float
    percent: float


class ResultOut(BaseModel):
    id: UUID
    exam_id: UUID | None
    exam_title: str | None
    kind: ResultKind
    title: str | None
    taken_on: date
    score: float
    max_score: float
    percent: float
    sections: list[SectionOut]
    weak_chapters: list[ChapterRef]
    notes: str | None
    created_at: UtcDatetime


class ExamDetailOut(ExamOut):
    readiness_detail: ReadinessOut | None = Field(
        description="Chapters, skills and reasons. Null once the test has passed"
    )
    revision: RevisionOut | None
    results: list[ResultOut]
