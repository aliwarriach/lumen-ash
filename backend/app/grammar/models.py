from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, OwnedMixin
from app.grammar.catalog import PatternKey


def str_enum(enum: type[StrEnum], name: str, length: int = 30) -> Enum:
    return Enum(
        enum,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [m.value for m in members],
        name=name,
    )


class GrammarEvidence(Base):
    """One right or wrong use of a grammar pattern. Accuracy is worked out from these rows.

    Comes from a logged mistake (always wrong), a checked review answer, or a grammar practice
    exercise (right or wrong). Deleting the mistake or the review removes its evidence.
    """

    __tablename__ = "grammar_evidence"
    __table_args__ = (
        Index("ix_grammar_evidence_user_pattern", "user_id", "pattern_key", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID]
    pattern_key: Mapped[PatternKey] = mapped_column(str_enum(PatternKey, "pattern_key"))
    correct: Mapped[bool]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mistake_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mistakes.id", ondelete="CASCADE"), index=True
    )
    review_log_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review_logs.id", ondelete="CASCADE"), index=True
    )
    # A practice answer: which exercise (app/grammar/exercises.py) and what the learner gave.
    exercise_id: Mapped[str | None] = mapped_column(String(20))
    given: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GrammarChapterLink(OwnedMixin, Base):
    """The learner's own link between a pattern and a chapter of their course."""

    __tablename__ = "grammar_chapter_links"
    __table_args__ = (
        UniqueConstraint("chapter_id", "pattern_key", name="uq_grammar_chapter_links_chapter"),
    )

    pattern_key: Mapped[PatternKey] = mapped_column(str_enum(PatternKey, "pattern_key"))
    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
