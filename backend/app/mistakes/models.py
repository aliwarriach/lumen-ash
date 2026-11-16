from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, OwnedMixin
from app.grammar.catalog import MistakeCategory, PatternKey
from app.grammar.models import str_enum
from app.vocabulary.models import VocabWord

mistake_words = Table(
    "mistake_words",
    Base.metadata,
    Column("mistake_id", ForeignKey("mistakes.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "word_id", ForeignKey("vocab_words.id", ondelete="CASCADE"), primary_key=True, index=True
    ),
)


class Mistake(OwnedMixin, Base):
    """One mistake the learner made, with its correction. Each becomes an error-retry card."""

    __tablename__ = "mistakes"

    wrong: Mapped[str] = mapped_column(Text)
    correct: Mapped[str] = mapped_column(Text)
    category: Mapped[MistakeCategory] = mapped_column(str_enum(MistakeCategory, "mistake_category"))
    pattern_key: Mapped[PatternKey | None] = mapped_column(str_enum(PatternKey, "pattern_key"))
    explanation: Mapped[str | None] = mapped_column(Text)
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str | None] = mapped_column(String(200))  # e.g. "Homework S. 31", "class"
    # The corrected version, normalised, so the same correction is recognised as a repeat.
    match_key: Mapped[str] = mapped_column(Text)
    # The earlier mistake this one repeats, if any.
    repeat_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mistakes.id", ondelete="SET NULL")
    )

    words: Mapped[list[VocabWord]] = relationship(
        secondary=mistake_words, lazy="selectin", order_by=VocabWord.german
    )
