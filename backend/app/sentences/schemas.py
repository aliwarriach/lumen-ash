from typing import Annotated

from pydantic import BaseModel, Field

from app.sentences.content import BlankRule, SentenceKind


class BlankOut(BaseModel):
    label: str
    example: str
    rule: BlankRule
    accepted: list[str]
    ends_with: str | None


class SentenceExerciseOut(BaseModel):
    id: str
    kind: SentenceKind
    prompt: str = Field(description="order/bank: the English; choice/fill/frame: German with ___")
    english: str | None
    options: list[str] = Field(description="choice only")
    tiles: list[str] = Field(description="order/bank: the sentence's words, then any extras")
    distractors: list[str] = Field(description="bank only: the tiles that don't belong")
    blanks: list[BlankOut] = Field(description="frame only: one per ___")
    answers: list[str] = Field(description="Accepted answers (frame: a model answer)")
    exact_case: bool = False
    end: str
    hint: str
    why: str


class LessonSummaryOut(BaseModel):
    id: str
    book_chapter: int | None = Field(description="null for the learner's own words")
    title: str
    topic: str
    exercise_count: int
    best_right: int | None = Field(description="null until the lesson has been done once")
    last_right: int | None
    rounds: int


class LessonOut(BaseModel):
    id: str
    book_chapter: int | None
    title: str
    topic: str
    exercises: list[SentenceExerciseOut]


class LessonResultIn(BaseModel):
    right: Annotated[int, Field(ge=0, le=100)]
    total: Annotated[int, Field(ge=1, le=100)]
