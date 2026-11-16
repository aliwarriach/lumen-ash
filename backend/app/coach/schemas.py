from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.coach.merge import Label, Source
from app.coach.models import CorrectionStatus
from app.core.types import UtcDatetime
from app.grammar.catalog import MistakeCategory, PatternKey

MAX_TEXT = 600

WritingText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
]
TaskPrompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

VERIFY_WARNING = "Verify with your teacher."


class CheckIn(BaseModel):
    text: WritingText = Field(description="German the learner wrote: one sentence or a few")
    task_id: UUID | None = Field(default=None, description="The writing task this is for")


class TaskIn(BaseModel):
    prompt: TaskPrompt
    min_sentences: int = Field(default=5, ge=1, le=20)


class TaskOut(BaseModel):
    id: UUID
    prompt: str
    min_sentences: int
    done: bool = Field(description="A check with enough sentences has been submitted")
    checks: int
    created_at: UtcDatetime


class CorrectionOut(BaseModel):
    id: UUID
    start: int
    end: int
    wrong: str
    correct: str
    sentence_wrong: str = Field(description="The whole sentence as written")
    sentence_correct: str = Field(description="The whole sentence, corrected")
    label: Label
    warning: str | None = Field(description="Set for 'uncertain' corrections")
    sources: list[Source] = Field(description="Which checkers found it")
    pattern_key: PatternKey | None
    pattern_title: str | None
    category: MistakeCategory
    explanation: str | None
    alternatives: list[str] = Field(description="Other possible fixes, if the checkers disagree")
    status: CorrectionStatus
    mistake_id: UUID | None = Field(description="The mistake-log entry, once accepted")


class CheckOut(BaseModel):
    id: UUID
    task_id: UUID | None
    text: str = Field(description="What was checked, with personal details removed")
    redacted: bool = Field(description="True if personal details were removed before checking")
    suggested_text: str | None = Field(
        description="The text with every confirmed and likely correction applied"
    )
    sentence_count: int
    corrections: list[CorrectionOut]
    explanation: str | None = Field(description="A short explanation at A1 level, from the AI")
    practice: list[str]
    practice_source: Literal["ai", "catalog"] | None
    checked_by: list[Literal["languagetool", "ai"]] = Field(
        description="Which checkers actually ran. Never empty: nothing is saved if none ran."
    )
    ai_status: Literal["ok", "cached", "limit", "unavailable", "error"]
    ai_message: str | None
    task_done: bool | None = Field(description="Whether this check completes its writing task")
    created_at: UtcDatetime
