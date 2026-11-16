from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints, UrlConstraints

from app.core.types import UtcDatetime
from app.course.models import ResourceKind

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
WebUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["http", "https"], max_length=2000)]
ChapterNumber = Annotated[int, Field(ge=1, le=99)]


class ChapterStatus(StrEnum):
    """Derived from resource completion. "needs_revision" arrives with review data (Phase 3)."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# --- Chapters ---


class ChapterCreate(BaseModel):
    number: ChapterNumber
    title: Title
    topics: Annotated[list[Topic], Field(max_length=30)] = []
    notes: Notes | None = None


class ChapterUpdate(BaseModel):
    number: ChapterNumber | None = None
    title: Title | None = None
    topics: Annotated[list[Topic], Field(max_length=30)] | None = None
    notes: Notes | None = None


class ChapterProgress(BaseModel):
    total: int
    completed: int
    status: ChapterStatus


class WordCounts(BaseModel):
    total: int = 0
    mastered: int = 0


class ChapterSummaryOut(BaseModel):
    id: UUID
    number: int
    title: str
    topics: list[str]
    progress: ChapterProgress
    words: WordCounts


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    kind: ResourceKind
    title: str
    reference: str | None
    url: str | None
    position: int
    completed_at: UtcDatetime | None


class ChapterOut(ChapterSummaryOut):
    notes: str | None
    resources: list[ResourceOut]


# --- Resources ---


class ResourceCreate(BaseModel):
    kind: ResourceKind
    title: Title
    reference: Reference | None = None
    url: WebUrl | None = None


class ResourceUpdate(BaseModel):
    kind: ResourceKind | None = None
    title: Title | None = None
    reference: Reference | None = None
    url: WebUrl | None = None
    completed: bool | None = None
