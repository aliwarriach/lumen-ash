"""Reading and writing the group chat.

Why every write takes a lock
----------------------------
A phone keeps up by remembering the highest `rev` it has seen and asking for "everything after
it". That is only safe if a row with a lower `rev` can never appear later. Numbers from a
Postgres sequence don't promise that: of two people posting at the same moment, the one who got
number 5 may commit after the one who got number 6, and a phone that had already seen 6 would
never ask for 5 again. The message would be missing on that phone for good.

So each write first takes one transaction-level advisory lock, and only then takes its number.
Writes to the chat happen one after the other, numbers are committed in order, and "everything
after N" never misses anything. The lock is held for one insert and its commit (a few
milliseconds), which is plenty for a room of people typing.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Row, Select, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.community.hub import Hub
from app.community.models import CommunityMessage, CommunityProfile, change_seq
from app.community.schemas import (
    MAX_BODY,
    CommunityAttachment,
    CommunityChangesOut,
    CommunityMeOut,
    CommunityMessageIn,
    CommunityMessageOut,
    CommunityPageOut,
    CommunityReplyOut,
    name_key,
)
from app.core.auth import CurrentUser
from app.core.config import Settings

# Any number, as long as nothing else in the app uses the same one.
WRITE_LOCK = 7_270_011
RATE_WINDOW = timedelta(seconds=60)
EXCERPT_CHARS = 140
NO_NAME = "Someone"  # an author whose profile is gone; can't happen through the API

NEED_NAME = "Choose a username before you post."
NAME_TAKEN = "Someone already uses that username. Try another."
NAME_LOCKED = "Your username can't be changed. Ask a moderator if it needs to be."
TOO_FAST = "You're sending messages very fast. Wait a few seconds and try again."
REPLY_GONE = "The message you are replying to is no longer there."
NOT_YOURS = "You can only delete your own messages."


@dataclass(frozen=True)
class CommunityRules:
    messages_per_minute: int
    moderators: frozenset[str]  # lower-case emails

    @classmethod
    def from_settings(cls, settings: Settings) -> "CommunityRules":
        return cls(settings.community_messages_per_minute, settings.community_moderators)

    def is_moderator(self, user: CurrentUser) -> bool:
        return user.email is not None and user.email.lower() in self.moderators


# --- Profiles ------------------------------------------------------------------------------------


async def me_out(session: AsyncSession, user: CurrentUser, rules: CommunityRules) -> CommunityMeOut:
    name = await session.scalar(
        select(CommunityProfile.display_name).where(CommunityProfile.user_id == user.id)
    )
    return CommunityMeOut(
        user_id=user.id,
        display_name=name,
        moderator=rules.is_moderator(user),
        max_message_chars=MAX_BODY,
        messages_per_minute=rules.messages_per_minute,
    )


async def set_name(
    session: AsyncSession, user: CurrentUser, name: str, rules: CommunityRules
) -> None:
    """Choose a username. It is fixed after that: only a moderator can change their own."""
    profile = await session.get(CommunityProfile, user.id)
    if profile is not None and not rules.is_moderator(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NAME_LOCKED)
    key = name_key(name)
    taken = await session.scalar(
        select(CommunityProfile.user_id).where(
            CommunityProfile.name_key == key, CommunityProfile.user_id != user.id
        )
    )
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, NAME_TAKEN)
    if profile is None:
        session.add(CommunityProfile(user_id=user.id, display_name=name, name_key=key))
    else:
        profile.display_name = name
        profile.name_key = key
    try:
        await session.commit()
    except IntegrityError as exc:
        # Two people chose the same name at the same moment: the database let one through.
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, NAME_TAKEN) from exc


# --- Reading -------------------------------------------------------------------------------------

_author = aliased(CommunityProfile)
_parent = aliased(CommunityMessage)
_parent_author = aliased(CommunityProfile)

# The joins are outer joins, so three of the four can be missing, whatever these types say:
# SQLAlchemy types a joined column by its table, not by the kind of join.
type _Row = Row[CommunityMessage, str, CommunityMessage, str]


def _messages() -> Select[CommunityMessage, str, CommunityMessage, str]:
    """A message with its author's name, and the message it answers with that author's name."""
    return (
        select(CommunityMessage, _author.display_name, _parent, _parent_author.display_name)
        .outerjoin(_author, _author.user_id == CommunityMessage.user_id)
        .outerjoin(_parent, _parent.id == CommunityMessage.reply_to_id)
        .outerjoin(_parent_author, _parent_author.user_id == _parent.user_id)
    )


def _excerpt(body: str) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[: EXCERPT_CHARS - 1].rstrip() + "…"


def _out(row: _Row) -> CommunityMessageOut:
    message: CommunityMessage = row[0]
    author_name: str | None = row[1]
    parent: CommunityMessage | None = row[2]
    parent_author_name: str | None = row[3]
    deleted = message.deleted_at is not None
    reply = None
    if parent is not None:
        reply = CommunityReplyOut(
            id=parent.id,
            author_name=parent_author_name or NO_NAME,
            excerpt=None if parent.deleted_at is not None else _excerpt(parent.body),
        )
    return CommunityMessageOut(
        id=message.id,
        seq=message.seq,
        rev=message.rev,
        author_id=message.user_id,
        author_name=author_name or NO_NAME,
        body=None if deleted else message.body,
        deleted=deleted,
        reply_to=reply,
        attachment=(
            None
            if deleted or message.attachment is None
            else CommunityAttachment.model_validate(message.attachment)
        ),
        created_at=message.created_at,
    )


async def current_rev(session: AsyncSession) -> int:
    return await session.scalar(select(func.max(CommunityMessage.rev))) or 0


async def page(session: AsyncSession, before: int | None, limit: int) -> CommunityPageOut:
    """The latest messages, or the ones before `before`. Oldest first."""
    # The cursor is read BEFORE the messages. A message posted between the two reads then shows
    # up twice (in this page and in the next "changes"), which is harmless; read the other way
    # round it could be missed.
    rev = await current_rev(session)
    query = _messages().order_by(CommunityMessage.seq.desc()).limit(limit + 1)
    if before is not None:
        query = query.where(CommunityMessage.seq < before)
    rows = list((await session.execute(query)).all())
    has_more = len(rows) > limit
    return CommunityPageOut(
        items=[_out(r) for r in reversed(rows[:limit])], has_more=has_more, rev=rev
    )


async def changes(session: AsyncSession, after: int, limit: int) -> CommunityChangesOut:
    """Messages posted or deleted since the phone last asked, in the order it happened."""
    query = (
        _messages()
        .where(CommunityMessage.rev > after)
        .order_by(CommunityMessage.rev)
        .limit(limit + 1)
    )
    rows = list((await session.execute(query)).all())
    items = [_out(r) for r in rows[:limit]]
    return CommunityChangesOut(
        items=items, rev=items[-1].rev if items else after, has_more=len(rows) > limit
    )


async def _one(session: AsyncSession, message_id: UUID) -> CommunityMessageOut:
    row = (await session.execute(_messages().where(CommunityMessage.id == message_id))).one()
    return _out(row)


# --- Writing -------------------------------------------------------------------------------------


def message_event(message: CommunityMessageOut) -> dict[str, Any]:
    return {"type": "message", "message": message.model_dump(mode="json")}


async def _lock_writes(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(WRITE_LOCK)))


async def _replayed(
    session: AsyncSession, user: CurrentUser, message_id: UUID
) -> CommunityMessageOut | None:
    """The message, if this id was already posted by this person (the phone is retrying)."""
    owner = await session.scalar(
        select(CommunityMessage.user_id).where(CommunityMessage.id == message_id)
    )
    if owner is None:
        return None
    if owner != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "That message id is already in use.")
    return await _one(session, message_id)


async def post(
    session: AsyncSession,
    hub: Hub,
    user: CurrentUser,
    body: CommunityMessageIn,
    rules: CommunityRules,
) -> CommunityMessageOut:
    # A retry of a message that did arrive: answer as before. Checked first, so a retry is never
    # refused for being "too fast".
    if (already := await _replayed(session, user, body.id)) is not None:
        return already

    has_name = await session.scalar(
        select(CommunityProfile.user_id).where(CommunityProfile.user_id == user.id)
    )
    if has_name is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NEED_NAME)

    recent = await session.scalar(
        select(func.count())
        .select_from(CommunityMessage)
        .where(
            CommunityMessage.user_id == user.id,
            CommunityMessage.created_at > func.now() - RATE_WINDOW,
        )
    )
    if (recent or 0) >= rules.messages_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, TOO_FAST, headers={"Retry-After": "15"}
        )

    if body.reply_to_id is not None:
        target = await session.scalar(
            select(CommunityMessage.id).where(
                CommunityMessage.id == body.reply_to_id, CommunityMessage.deleted_at.is_(None)
            )
        )
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, REPLY_GONE)

    await _lock_writes(session)
    inserted = await session.scalar(
        pg_insert(CommunityMessage)
        .values(
            id=body.id,
            user_id=user.id,
            body=body.body,
            reply_to_id=body.reply_to_id,
            attachment=body.attachment.model_dump() if body.attachment else None,
        )
        .on_conflict_do_nothing(index_elements=[CommunityMessage.id])
        .returning(CommunityMessage.id)
    )
    await session.commit()
    if inserted is None:
        # The same send arrived twice at once and the other copy won. Nothing new to announce.
        if (already := await _replayed(session, user, body.id)) is not None:
            return already
        raise HTTPException(status.HTTP_409_CONFLICT, "That message id is already in use.")

    out = await _one(session, body.id)
    hub.publish(message_event(out))
    return out


async def delete(
    session: AsyncSession,
    hub: Hub,
    user: CurrentUser,
    message_id: UUID,
    rules: CommunityRules,
) -> CommunityMessageOut:
    """Empties a message and marks it deleted. Doing it twice is fine."""
    found = (
        await session.execute(
            select(CommunityMessage.user_id, CommunityMessage.deleted_at).where(
                CommunityMessage.id == message_id
            )
        )
    ).one_or_none()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    owner, deleted_at = found
    if owner != user.id and not rules.is_moderator(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_YOURS)
    if deleted_at is not None:
        return await _one(session, message_id)

    await _lock_writes(session)
    changed = await session.scalar(
        update(CommunityMessage)
        .where(CommunityMessage.id == message_id, CommunityMessage.deleted_at.is_(None))
        .values(
            body="",
            attachment=None,
            deleted_at=func.now(),
            deleted_by=user.id,
            rev=change_seq.next_value(),
        )
        .returning(CommunityMessage.id)
    )
    await session.commit()
    out = await _one(session, message_id)
    if changed is not None:
        hub.publish(message_event(out))
    return out
