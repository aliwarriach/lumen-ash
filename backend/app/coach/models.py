from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.coach.merge import Label
from app.core.database import Base, OwnedMixin
from app.grammar.catalog import MistakeCategory, PatternKey
from app.grammar.models import str_enum


class Decision(StrEnum):
    """What the learner can do with a correction."""

    ACCEPT = "accept"
    REJECT = "reject"
    FLAG = "flag"


class CorrectionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FLAGGED = "flagged"  # the learner thinks it is wrong, or wants to ask the teacher


class WritingTask(OwnedMixin, Base):
    """A writing prompt, e.g. "5 sentences about your day". Done when one check meets the count."""

    __tablename__ = "writing_tasks"

    prompt: Mapped[str] = mapped_column(String(200))
    min_sentences: Mapped[int] = mapped_column(Integer, default=5, server_default="5")


class CoachCheck(OwnedMixin, Base):
    """One piece of writing that was checked. `text` is what was actually checked, with personal
    details already removed (see ai/redact.py)."""

    __tablename__ = "coach_checks"

    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("writing_tasks.id", ondelete="SET NULL"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    redacted: Mapped[bool] = mapped_column(default=False, server_default="false")
    suggested_text: Mapped[str | None] = mapped_column(Text)
    sentence_count: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)
    practice: Mapped[list[str]] = mapped_column(JSONB, default=list)
    practice_source: Mapped[str | None] = mapped_column(String(10))  # "ai" or "catalog"
    checked_by: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ai_status: Mapped[str] = mapped_column(String(20))
    ai_message: Mapped[str | None] = mapped_column(Text)


class CoachCorrection(OwnedMixin, Base):
    __tablename__ = "coach_corrections"

    check_id: Mapped[UUID] = mapped_column(
        ForeignKey("coach_checks.id", ondelete="CASCADE"), index=True
    )
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    wrong: Mapped[str] = mapped_column(Text)
    correct: Mapped[str] = mapped_column(Text)
    # The whole sentence as written and corrected: what goes in the mistake log when accepted.
    sentence_wrong: Mapped[str] = mapped_column(Text)
    sentence_correct: Mapped[str] = mapped_column(Text)
    label: Mapped[Label] = mapped_column(str_enum(Label, "coach_label"))
    pattern_key: Mapped[PatternKey | None] = mapped_column(str_enum(PatternKey, "pattern_key"))
    category: Mapped[MistakeCategory] = mapped_column(str_enum(MistakeCategory, "mistake_category"))
    explanation: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[str]] = mapped_column(JSONB, default=list)
    alternatives: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[CorrectionStatus] = mapped_column(
        str_enum(CorrectionStatus, "correction_status"),
        default=CorrectionStatus.PENDING,
        server_default="pending",
    )
    mistake_id: Mapped[UUID | None] = mapped_column(ForeignKey("mistakes.id", ondelete="SET NULL"))
