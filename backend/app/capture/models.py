from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, OwnedMixin
from app.grammar.models import str_enum


class TaskKind(StrEnum):
    """Mirrors `CAPTURE_KINDS` in app/ai/prompts.py."""

    HOMEWORK = "homework"
    DEADLINE = "deadline"
    TEST = "test"
    EVENT = "event"
    OTHER = "other"


class ClassTask(OwnedMixin, Base):
    """Something from the class chat the learner has to do, saved after they approved it.

    Only the approved task is kept. The message it came from is never stored: it holds other
    people's names and numbers (see docs/build-history.md, Phase 10).
    """

    __tablename__ = "class_tasks"

    kind: Mapped[TaskKind] = mapped_column(
        str_enum(TaskKind, "class_task_kind"), default=TaskKind.HOMEWORK, server_default="homework"
    )
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    # The date words as written in the message ("Freitag"), kept to show where the date came from.
    due_text: Mapped[str | None] = mapped_column(String(40))
    url: Mapped[str | None] = mapped_column(Text)
    # When the phone should remind the learner. The phone schedules it; this is the source of truth
    # so the reminder can be set up again after a reinstall.
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
