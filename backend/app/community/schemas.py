import unicodedata
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.core.types import UtcDatetime

MAX_BODY = 2000
USERNAME_MIN = 3
USERNAME_MAX = 20
# Letters, digits and underscores only (plus the German letters): no spaces, no look-alike
# alphabets, nothing that could pass for punctuation or a different person's name.
USERNAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_äöüßÄÖÜ")
# Names that sound official. Compared after case-folding and dropping underscores and digits.
RESERVED_USERNAMES = frozenset(
    {
        "admin",
        "administrator",
        "moderator",
        "mod",
        "staff",
        "support",
        "official",
        "system",
        "teacher",
        "lehrer",
        "lehrerin",
        "lumen",
        "lumena",
        "someone",
        "everyone",
        "anonymous",
    }
)
PAGE_DEFAULT = 50
PAGE_MAX = 100
CHANGES_MAX = 200

# "Ask the Community": the thing a question is about, shared as a small card above it.
ATTACHMENT_TITLE_MAX = 120
ATTACHMENT_LINE_MAX = 300
ATTACHMENT_LINES_MAX = 6
AttachmentKind = Literal["word", "exercise", "lesson", "grammar", "resource"]


def _printable(ch: str) -> bool:
    """False for control characters, and for the invisible ones (zero-width, direction marks)
    that could make two names look the same or a message look empty."""
    return unicodedata.category(ch) not in {"Cc", "Cf", "Cs", "Co", "Cn"}


def clean_body(value: str) -> str:
    # Newlines and tabs are kept (people write lists); every other control character goes. A NUL
    # in particular would make Postgres refuse the row.
    value = "".join(ch for ch in value if ch in "\n\t" or _printable(ch)).strip()
    if not value:
        raise ValueError("Write a message first.")
    if len(value) > MAX_BODY:
        raise ValueError(f"A message can be at most {MAX_BODY} characters.")
    return value


def clean_username(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    if not USERNAME_MIN <= len(value) <= USERNAME_MAX:
        raise ValueError(f"A username must be {USERNAME_MIN} to {USERNAME_MAX} characters.")
    if any(ch not in USERNAME_CHARS for ch in value):
        raise ValueError("Use only letters, numbers and underscores (_), with no spaces.")
    if not any(ch.isalpha() for ch in value):
        raise ValueError("A username needs at least one letter.")
    plain = "".join(ch for ch in value.casefold() if ch.isalpha())
    if plain in RESERVED_USERNAMES:
        raise ValueError("That username is reserved. Please choose another.")
    return value


def name_key(name: str) -> str:
    """What makes two names "the same": case, accents-as-typed and width don't count."""
    return unicodedata.normalize("NFKC", name).casefold()


def _clean_line(value: str, limit: int) -> str:
    """One line of a card: no control characters, spaces collapsed, cut to `limit`."""
    flat = " ".join("".join(ch if _printable(ch) else " " for ch in value).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


MessageBody = Annotated[str, AfterValidator(clean_body)]
Username = Annotated[str, AfterValidator(clean_username)]


class CommunityMeIn(BaseModel):
    display_name: Username = Field(
        description="The username other people see. Unique, and fixed once chosen."
    )


class CommunityMeOut(BaseModel):
    user_id: UUID
    display_name: str | None = Field(description="Null until the person has chosen a name")
    moderator: bool = Field(description="May delete anyone's message")
    max_message_chars: int
    messages_per_minute: int


class CommunityAttachment(BaseModel):
    """What a question is about (a word, an exercise, a lesson, a grammar rule, a course
    resource), as the asker's phone described it. Plain text only: no links, no ids, nothing
    another person's phone would open. Long lines are shortened rather than refused."""

    kind: AttachmentKind
    title: str = Field(description=f"At most {ATTACHMENT_TITLE_MAX} characters")
    lines: list[str] = Field(
        default_factory=list,
        description=(
            f"Up to {ATTACHMENT_LINES_MAX} lines of at most {ATTACHMENT_LINE_MAX} characters"
        ),
    )

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = _clean_line(value, ATTACHMENT_TITLE_MAX)
        if not value:
            raise ValueError("A shared item needs a title.")
        return value

    @field_validator("lines")
    @classmethod
    def _lines(cls, value: list[str]) -> list[str]:
        if len(value) > ATTACHMENT_LINES_MAX:
            raise ValueError(f"A shared item can have at most {ATTACHMENT_LINES_MAX} lines.")
        cleaned = (_clean_line(line, ATTACHMENT_LINE_MAX) for line in value)
        return [line for line in cleaned if line]


class CommunityMessageIn(BaseModel):
    id: UUID = Field(description="Made up by the phone. Sending the same id again posts nothing.")
    body: MessageBody
    reply_to_id: UUID | None = None
    attachment: CommunityAttachment | None = Field(
        default=None, description="What the question is about (Ask the Community)"
    )


class CommunityReplyOut(BaseModel):
    """The message being answered, shortened."""

    id: UUID
    author_name: str
    excerpt: str | None = Field(description="Null when that message has been deleted")


class CommunityMessageOut(BaseModel):
    id: UUID
    seq: int = Field(description="Place in the conversation: higher is later")
    rev: int = Field(description="Changes when the message does; see GET /community/changes")
    author_id: UUID
    author_name: str
    body: str | None = Field(description="Null when the message has been deleted")
    deleted: bool
    reply_to: CommunityReplyOut | None
    attachment: CommunityAttachment | None = Field(
        description="The shared item, if any. Null when the message has been deleted"
    )
    created_at: UtcDatetime


class CommunityPageOut(BaseModel):
    items: list[CommunityMessageOut] = Field(description="Oldest first")
    has_more: bool = Field(description="There are older messages before the first item")
    rev: int = Field(description="Ask GET /community/changes for what happens after this")


class CommunityChangesOut(BaseModel):
    items: list[CommunityMessageOut] = Field(description="New and changed messages, by `rev`")
    rev: int = Field(description="Pass as `after` next time")
    has_more: bool = Field(description="More changes than fit: load the latest page instead")
