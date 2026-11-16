from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import CheckConstraint

from app.core.database import Base, OwnedMixin
from app.course.models import Chapter
from app.grammar.models import str_enum

DEFAULT_TARGET_PERCENT = 85  # the learner's goal from the product design


class ExamKind(StrEnum):
    INTERNAL = "internal"  # an ASH assessment
    GOETHE_A1 = "goethe_a1"


class ResultKind(StrEnum):
    PRACTICE = "practice"  # a practice or mock test
    EXAM = "exam"  # the real thing, recorded afterwards


class Skill(StrEnum):
    """Skills a test result can be broken down by. Reading, listening, writing and speaking are
    not tracked by the app itself, so they only appear if the learner enters section scores."""

    READING = "reading"
    LISTENING = "listening"
    WRITING = "writing"
    SPEAKING = "speaking"
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"


exam_chapters = Table(
    "exam_chapters",
    Base.metadata,
    Column("exam_id", ForeignKey("exams.id", ondelete="CASCADE"), primary_key=True),
    Column("chapter_id", ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True),
)

exam_result_chapters = Table(
    "exam_result_chapters",
    Base.metadata,
    Column("result_id", ForeignKey("exam_results.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "chapter_id",
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Exam(OwnedMixin, Base):
    """A test the learner is preparing for: an internal ASH test or the Goethe A1 exam."""

    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint("target_percent BETWEEN 1 AND 100", name="target_percent_range"),
    )

    kind: Mapped[ExamKind] = mapped_column(str_enum(ExamKind, "exam_kind"))
    title: Mapped[str] = mapped_column(String(200))
    exam_date: Mapped[date] = mapped_column(Date, index=True)
    # The Goethe exam covers the whole course; an internal test usually covers some chapters.
    # Kept as a flag so deleting a chapter can never turn a chapter test into a whole-course one.
    whole_course: Mapped[bool] = mapped_column(default=True, server_default="true")
    target_percent: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_TARGET_PERCENT, server_default=str(DEFAULT_TARGET_PERCENT)
    )
    notes: Mapped[str | None] = mapped_column(Text)

    chapters: Mapped[list[Chapter]] = relationship(
        secondary=exam_chapters, lazy="selectin", order_by=Chapter.number
    )


class ExamResult(OwnedMixin, Base):
    """A score the learner entered: a practice test, or the real result afterwards."""

    __tablename__ = "exam_results"
    __table_args__ = (
        CheckConstraint("max_score > 0", name="max_score_positive"),
        CheckConstraint("score >= 0 AND score <= max_score", name="score_in_range"),
    )

    exam_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exams.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ResultKind] = mapped_column(str_enum(ResultKind, "result_kind"))
    title: Mapped[str | None] = mapped_column(String(200))
    taken_on: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    # Optional section scores: [{"skill": "listening", "score": 18, "max_score": 25}, ...]
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    # Chapters the learner lost marks on: they count as weak areas in readiness.
    weak_chapters: Mapped[list[Chapter]] = relationship(
        secondary=exam_result_chapters, lazy="selectin", order_by=Chapter.number
    )
