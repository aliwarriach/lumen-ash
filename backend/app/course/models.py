from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, OwnedMixin


class ResourceKind(StrEnum):
    BOOK_PAGE = "book_page"
    WORKBOOK_EXERCISE = "workbook_exercise"
    AUDIO = "audio"
    VIDEO = "video"
    EXERCISE = "exercise"
    OTHER = "other"


class Chapter(OwnedMixin, Base):
    """One chapter of the learner's course, e.g. Kapitel 3 of Netzwerk neu A1."""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("user_id", "number", name="uq_chapters_user_number"),
        CheckConstraint("number >= 1", name="number_positive"),
    )

    number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(200)), server_default="{}")
    notes: Mapped[str | None] = mapped_column(Text)

    resources: Mapped[list["ChapterResource"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChapterResource.position",
    )


class ChapterResource(OwnedMixin, Base):
    """A link or reference for a chapter: a book page, Allango audio, a workbook exercise...

    Only references and links are stored, never copyrighted files.
    """

    __tablename__ = "chapter_resources"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ResourceKind] = mapped_column(
        Enum(
            ResourceKind,
            native_enum=False,
            create_constraint=True,
            length=32,
            values_callable=lambda kinds: [k.value for k in kinds],
            name="resource_kind",
        )
    )
    title: Mapped[str] = mapped_column(String(200))
    # Where to find it in the book, e.g. "S. 24, Ü 3".
    reference: Mapped[str | None] = mapped_column(String(100))
    # Allango or other authorised link.
    url: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chapter: Mapped[Chapter] = relationship(back_populates="resources")
