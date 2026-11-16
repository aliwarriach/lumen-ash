from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.capture.models import TaskKind
from app.core.types import UtcDatetime

# A pasted chat can be long; the AI layer rejects what is too long for it with a clear message.
MAX_MESSAGE = 20_000
MAX_TASKS_AT_ONCE = 10

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE)
]


def _web_link(value: str) -> str:
    """Links are opened on the phone, so only plain web links are accepted."""
    value = value.strip()
    if not value.lower().startswith(("http://", "https://")) or len(value) > 2000:
        raise ValueError("Links must start with http:// or https://")
    if any(c.isspace() for c in value):
        raise ValueError("A link can't contain spaces")
    return value


WebLink = Annotated[str, AfterValidator(_web_link)]


class ScanIn(BaseModel):
    text: MessageText = Field(description="The message the learner shared or pasted")


class ProposedTaskOut(BaseModel):
    kind: TaskKind
    title: str
    due_date: date | None = Field(description="Worked out from the date words; null if unclear")
    due_text: str | None = Field(description="The date words as written in the message")
    url: str | None = Field(description="Set when the message has exactly one link")
    duplicate: bool = Field(description="An open task with the same title already exists")


class ScanOut(BaseModel):
    items: list[ProposedTaskOut]
    links: list[str] = Field(description="Every link in the message, found without AI")
    message: str | None = Field(description="Set when nothing was found")


class ClassTaskIn(BaseModel):
    kind: TaskKind = TaskKind.HOMEWORK
    title: Title
    due_date: date | None = None
    due_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    url: WebLink | None = None
    remind_at: UtcDatetime | None = None


class ClassTaskBatchIn(BaseModel):
    items: list[ClassTaskIn] = Field(min_length=1, max_length=MAX_TASKS_AT_ONCE)


class ClassTaskUpdate(BaseModel):
    """Only the fields sent are changed. `kind` and `title` can't be set to null."""

    kind: TaskKind | None = None
    title: Title | None = None
    due_date: date | None = None
    due_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    url: WebLink | None = None
    remind_at: UtcDatetime | None = None
    done: bool | None = None


class ClassTaskOut(BaseModel):
    id: UUID
    kind: TaskKind
    title: str
    due_date: date | None
    due_text: str | None
    days_left: int | None = Field(description="Negative when overdue; null with no date")
    url: str | None
    remind_at: UtcDatetime | None
    done: bool
    done_at: UtcDatetime | None
    created_at: UtcDatetime
