from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.types import UtcDatetime
from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey
from app.review.grading import normalize
from app.vocabulary.forms import Article, WordKind

Sentence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Explanation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
WordIds = Annotated[list[UUID], Field(max_length=20)]


def check_versions_differ(wrong: str, correct: str) -> None:
    if normalize(wrong) == normalize(correct):
        raise ValueError("The corrected version is the same as the wrong one")


class MistakeCreate(BaseModel):
    wrong: Sentence = Field(description="What the learner wrote or said")
    correct: Sentence = Field(description="The corrected version")
    category: MistakeCategory | None = Field(
        default=None, description="Defaults to the grammar pattern's category"
    )
    pattern_key: PatternKey | None = None
    explanation: Explanation | None = None
    chapter_id: UUID | None = None
    source: Short | None = None
    word_ids: WordIds = []

    @model_validator(mode="after")
    def complete(self) -> Self:
        check_versions_differ(self.wrong, self.correct)
        if self.category is None:
            if self.pattern_key is None:
                raise ValueError("Choose a category or a grammar pattern")
            self.category = PATTERNS[self.pattern_key].category
        return self


class MistakeUpdate(BaseModel):
    """Partial update. wrong, correct, category and word_ids can't be set to null."""

    wrong: Sentence | None = None
    correct: Sentence | None = None
    category: MistakeCategory | None = None
    pattern_key: PatternKey | None = None
    explanation: Explanation | None = None
    chapter_id: UUID | None = None
    source: Short | None = None
    word_ids: WordIds | None = None


class MistakeWordOut(BaseModel):
    id: UUID
    kind: WordKind
    german: str
    article: Article | None


class RepeatOfOut(BaseModel):
    id: UUID
    wrong: str
    created_at: UtcDatetime
    reason: str = Field(description="Why it counts as a repeat")


class RetryOut(BaseModel):
    due: UtcDatetime
    retries: int = Field(description="Times the learner has retried this mistake")
    last_correct: bool | None


class MistakeOut(BaseModel):
    id: UUID
    wrong: str
    correct: str
    category: MistakeCategory
    pattern_key: PatternKey | None
    pattern_title: str | None
    explanation: str | None
    chapter_id: UUID | None
    source: str | None
    words: list[MistakeWordOut]
    repeat_of: RepeatOfOut | None
    retry: RetryOut | None
    created_at: UtcDatetime


class CategoryCount(BaseModel):
    category: MistakeCategory
    total: int
    last_30_days: int
    repeats: int


class PatternCount(BaseModel):
    key: PatternKey
    title: str
    total: int
    last_30_days: int
    repeats: int


class MistakeSummaryOut(BaseModel):
    total: int
    last_30_days: int
    repeats: int
    by_category: list[CategoryCount] = Field(description="Most mistakes first")
    by_pattern: list[PatternCount] = Field(description="Most mistakes first")
