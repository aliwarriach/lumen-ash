from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiUsage(Base):
    """What one learner used on one UTC day, per feature and provider.

    Every limit is a sum over these rows: the learner's total, their per-feature count, and each
    provider's total across all learners (the shared ceiling). Nothing needs resetting: a new
    date is simply a new set of rows.
    """

    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_date_provider", "usage_date", "provider"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    feature: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiBurst(Base):
    """The short-burst throttle: one row per learner holding a one-minute counting window."""

    __tablename__ = "ai_burst"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer)


class AiCache(Base):
    """Answers we've already paid for. Shared by all learners: the key is the redacted prompt."""

    __tablename__ = "ai_cache"

    # sha256 of the feature, template version and normalised prompt.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature: Mapped[str] = mapped_column(String(40))
    template_version: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
