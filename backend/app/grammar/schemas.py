from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.types import UtcDatetime
from app.grammar.catalog import MistakeCategory, PatternKey
from app.grammar.exercises import ExerciseKind


class PatternLevel(StrEnum):
    NOT_ENOUGH_DATA = "not_enough_data"  # fewer than 3 attempts in the last 30 days
    WEAK = "weak"  # under 70% right
    OK = "ok"  # 70-89%
    STRONG = "strong"  # 90% or more


class EvidenceSource(StrEnum):
    MISTAKE = "mistake"
    REVIEW = "review"
    PRACTICE = "practice"


class ExampleOut(BaseModel):
    german: str
    english: str


class CommonMistakeOut(BaseModel):
    wrong: str
    correct: str
    why: str


class PracticeOut(BaseModel):
    prompt: str
    answer: str


class PatternStatsOut(BaseModel):
    attempts: int = Field(description="Checked uses of this pattern in the last 30 days")
    correct: int
    accuracy: float | None = Field(description="0-1 over the last 30 days; null if no attempts")
    previous_accuracy: float | None = Field(description="The same for the 30 days before that")
    level: PatternLevel
    mistakes: int = Field(description="Logged mistakes for this pattern, all time")
    repeats: int = Field(description="How many of those repeat an earlier mistake")
    last_mistake_at: UtcDatetime | None


class PatternSummaryOut(BaseModel):
    key: PatternKey
    title: str
    category: MistakeCategory
    chapter_ids: list[UUID]
    book_chapter: int = Field(description="The Netzwerk neu A1 chapter that first teaches it")
    exercise_count: int
    stats: PatternStatsOut


class EvidenceOut(BaseModel):
    pattern_key: PatternKey
    correct: bool
    occurred_at: UtcDatetime
    source: EvidenceSource
    label: str = Field(description="Where it came from, e.g. 'Article card', 'Logged mistake'")
    given: str | None
    expected: str | None
    mistake_id: UUID | None
    word_id: UUID | None


class PatternOut(PatternSummaryOut):
    explanation: str
    examples: list[ExampleOut]
    common_mistakes: list[CommonMistakeOut]
    practice: list[PracticeOut]
    evidence: list[EvidenceOut] = Field(description="Most recent first")


class WeakPatternOut(BaseModel):
    key: PatternKey
    title: str
    category: MistakeCategory
    stats: PatternStatsOut
    reason: str = Field(description="Why it is listed, in one sentence")
    evidence: list[EvidenceOut] = Field(description="The most recent wrong answers")


class PatternChaptersIn(BaseModel):
    chapter_ids: Annotated[list[UUID], Field(max_length=50)]


class ExerciseOut(BaseModel):
    id: str
    kind: ExerciseKind
    prompt: str = Field(description="choice/fill: the German with ___ ; order: the English")
    english: str | None
    options: list[str] = Field(description="choice only")
    tiles: list[str] = Field(description="order only, in the right order: shuffle before showing")
    answers: list[str] = Field(description="Accepted answers, the first is the one to show")
    exact_case: bool
    end: str = Field(description="order only: the punctuation after the tiles")
    hint: str
    why: str


class PracticeSetOut(BaseModel):
    key: PatternKey
    title: str
    book_chapter: int
    exercises: list[ExerciseOut]


class PracticeAnswerIn(BaseModel):
    exercise_id: Annotated[str, Field(min_length=1, max_length=20)]
    given: Annotated[str, Field(max_length=300)]


class PracticeAnswerOut(BaseModel):
    correct: bool
    expected: str
    pattern_key: PatternKey
