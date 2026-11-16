from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, OwnedMixin


class SentenceResult(OwnedMixin, Base):
    """A learner's score on one sentence lesson: the best round and the latest."""

    __tablename__ = "sentence_results"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_sentence_results_lesson"),)

    lesson_id: Mapped[str] = mapped_column(String(30))
    best_right: Mapped[int]
    last_right: Mapped[int]
    total: Mapped[int]
    rounds: Mapped[int]
