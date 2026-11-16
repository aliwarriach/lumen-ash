"""The community forum: one group chat shared by everyone who can sign in.

These are the only tables that are NOT private to one learner. Everything else in the app is
filtered by `user_id`; here every signed-in person reads every row, and `user_id` only says who
wrote it.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Sequence, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# One counter for the whole chat. A message takes two numbers from it when it is posted (`seq`,
# its place in the conversation, and `rev`) and a new `rev` whenever it changes (today: when it
# is deleted). A phone remembers the highest `rev` it has seen and asks for "everything after
# it", which brings new messages and deletions alike. See service.py for why writes take a lock.
change_seq = Sequence("community_change_seq", metadata=Base.metadata)

NAME_MAX = 24


class CommunityProfile(Base):
    """The name a person goes by in the chat. Emails are never shown to other people."""

    __tablename__ = "community_profiles"

    # The Supabase auth user id. Not a foreign key: auth.users lives in Supabase's own schema.
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(NAME_MAX))
    # The name with case and look-alike forms folded, so "Ali" and "ALI" can't both exist.
    # Folding can lengthen a name ("ß" becomes "ss"), hence the wider column.
    name_key: Mapped[str] = mapped_column(String(NAME_MAX * 3), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommunityMessage(Base):
    __tablename__ = "community_messages"
    __table_args__ = (
        # "How many messages has this person posted in the last minute?"
        Index("ix_community_messages_user_id_created_at", "user_id", "created_at"),
    )

    # Chosen by the phone, so a send that is retried after a dropped connection is recognised
    # and never posted twice.
    id: Mapped[UUID] = mapped_column(primary_key=True)
    seq: Mapped[int] = mapped_column(
        BigInteger, server_default=change_seq.next_value(), unique=True
    )
    rev: Mapped[int] = mapped_column(BigInteger, server_default=change_seq.next_value(), index=True)
    user_id: Mapped[UUID] = mapped_column()
    # Emptied when the message is deleted: a deleted message is really gone.
    body: Mapped[str] = mapped_column(Text)
    reply_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("community_messages.id", ondelete="SET NULL")
    )
    # "Ask the Community": the shared item (kind, title, lines) as validated by
    # schemas.CommunityAttachment. Emptied with the body when the message is deleted.
    attachment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[UUID | None] = mapped_column()
