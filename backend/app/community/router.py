"""The community forum's API: plain requests to read and write, and one socket that pushes what
is new to every phone that is connected.

The socket only ever sends. Posting and deleting go through the ordinary endpoints, so they get
the same checks, the same errors and the same retries as everything else in the app, and the
chat keeps working (a little slower) for a phone whose socket can't connect at all.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, status
from starlette.concurrency import run_in_threadpool

from app.community import service
from app.community.hub import (
    CLOSE_BAD_REQUEST,
    CLOSE_IDLE,
    CLOSE_TRY_LATER,
    CLOSE_UNAUTHORIZED,
    Connection,
    Hub,
    HubFull,
)
from app.community.schemas import (
    CHANGES_MAX,
    PAGE_DEFAULT,
    PAGE_MAX,
    CommunityChangesOut,
    CommunityMeIn,
    CommunityMeOut,
    CommunityMessageIn,
    CommunityMessageOut,
    CommunityPageOut,
)
from app.community.service import CommunityRules
from app.core.auth import (
    CurrentUserDep,
    SignInServiceDown,
    TokenRejected,
    VerifiedToken,
    verify_token,
)
from app.core.config import get_settings
from app.core.database import SessionDep

log = logging.getLogger(__name__)

router = APIRouter(tags=["community"])

AUTH_TIMEOUT_SECONDS = 15.0  # how long a new socket has to say who it is
# The phone pings every 25 seconds. Three missed pings and the connection is taken for dead, so
# "people here now" doesn't count phones that walked out of signal.
IDLE_TIMEOUT_SECONDS = 80.0
MAX_FRAME_CHARS = 8192  # a login token is about 1,000; nothing else the phone sends is longer

TokenVerifier = Callable[[str], VerifiedToken]


@lru_cache
def get_hub() -> Hub:
    return Hub(max_connections=get_settings().community_max_connections)


@lru_cache
def get_rules() -> CommunityRules:
    return CommunityRules.from_settings(get_settings())


def get_token_verifier() -> TokenVerifier:
    return verify_token


HubDep = Annotated[Hub, Depends(get_hub)]
RulesDep = Annotated[CommunityRules, Depends(get_rules)]


@router.get("/community/me")
async def community_me(
    user: CurrentUserDep, session: SessionDep, rules: RulesDep
) -> CommunityMeOut:
    """Who I am in the chat. `display_name` is null until one is chosen."""
    return await service.me_out(session, user, rules)


@router.put("/community/me")
async def set_community_name(
    body: CommunityMeIn, user: CurrentUserDep, session: SessionDep, rules: RulesDep
) -> CommunityMeOut:
    """Choose the username other people see (once; 403 if already set unless a moderator).
    409 if someone else has it."""
    await service.set_name(session, user, body.display_name, rules)
    return await service.me_out(session, user, rules)


@router.get("/community/messages")
async def list_messages(
    _: CurrentUserDep,
    session: SessionDep,
    before: Annotated[int | None, Query(ge=1, description="A `seq`: load older than this")] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> CommunityPageOut:
    """The latest messages (or, with `before`, an older page), oldest first."""
    return await service.page(session, before, limit)


@router.get("/community/changes")
async def list_changes(
    _: CurrentUserDep,
    session: SessionDep,
    after: Annotated[int, Query(ge=0, description="The `rev` from the last answer")],
    limit: Annotated[int, Query(ge=1, le=CHANGES_MAX)] = CHANGES_MAX,
) -> CommunityChangesOut:
    """Everything posted or deleted since `after`. This is how a phone stays up to date, with or
    without the live socket."""
    return await service.changes(session, after, limit)


@router.post("/community/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    body: CommunityMessageIn,
    user: CurrentUserDep,
    session: SessionDep,
    hub: HubDep,
    rules: RulesDep,
) -> CommunityMessageOut:
    """Post a message. The phone makes up the id, so sending it again after a lost connection
    returns the message that was already saved instead of posting it twice."""
    return await service.post(session, hub, user, body, rules)


@router.delete("/community/messages/{message_id}")
async def delete_message(
    message_id: UUID, user: CurrentUserDep, session: SessionDep, hub: HubDep, rules: RulesDep
) -> CommunityMessageOut:
    """Delete your own message (a moderator: anyone's). Its text is erased, and everyone sees
    "message deleted" in its place."""
    return await service.delete(session, hub, user, message_id, rules)


# --- The live socket -----------------------------------------------------------------------------


def _field(text: str, kind: str, name: str | None = None) -> str | None:
    """`name` from a JSON frame of the given `type` ("" when no field is asked for)."""
    if len(text) > MAX_FRAME_CHARS:
        return None
    try:
        frame = json.loads(text)
    except ValueError:
        return None
    if not isinstance(frame, dict) or frame.get("type") != kind:
        return None
    if name is None:
        return ""
    value = frame.get(name)
    return value if isinstance(value, str) else None


async def _receive(websocket: WebSocket, hub: Hub, connection: Connection, expires_at: int) -> int:
    """Answers pings until the login runs out or the phone goes quiet. Returns the close code."""
    while True:
        remaining = expires_at - time.time()
        if remaining <= 0:
            return CLOSE_UNAUTHORIZED
        try:
            text = await asyncio.wait_for(
                websocket.receive_text(), timeout=min(IDLE_TIMEOUT_SECONDS, remaining)
            )
        except TimeoutError:
            if time.time() >= expires_at:
                return CLOSE_UNAUTHORIZED
            return CLOSE_IDLE
        if _field(text, "ping") is not None:
            hub.send(connection, {"type": "pong"})
        # Anything else is ignored: this socket is for listening.


async def _send(websocket: WebSocket, connection: Connection) -> int:
    """Writes queued events to the phone. Returns when the hub drops the connection."""
    while True:
        text = await connection.queue.get()
        if text is None:
            return connection.close_code or CLOSE_TRY_LATER
        await websocket.send_text(text)


@router.websocket("/community/ws")
async def community_socket(
    websocket: WebSocket,
    hub: HubDep,
    verify: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> None:
    """Pushes new and deleted messages, and how many people are here.

    The phone must send `{"type": "auth", "token": "<access token>"}` first: a WebSocket can't
    carry the Authorization header from every client, and a token in the URL would end up in
    logs. Then the server sends `ready`, and after that `message`, `presence` and `pong`. The
    phone sends `{"type": "ping"}` now and then. The socket is closed when the token expires
    (4401); the phone reconnects with a fresh one.
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    except TimeoutError:
        await websocket.close(CLOSE_UNAUTHORIZED)
        return
    except Exception:  # the phone went away before saying anything
        return
    token = _field(first, "auth", "token")
    if not token:
        await websocket.close(CLOSE_BAD_REQUEST)
        return
    try:
        verified = await run_in_threadpool(verify, token)
    except TokenRejected:
        await websocket.close(CLOSE_UNAUTHORIZED)
        return
    except SignInServiceDown:
        await websocket.close(CLOSE_TRY_LATER)
        return

    try:
        connection = hub.join(verified.user.id)
    except HubFull:
        log.warning("Community chat is full (%d connections)", hub.connections)
        await websocket.close(CLOSE_TRY_LATER)
        return

    hub.send(connection, {"type": "ready", "online": hub.online})
    tasks = [
        asyncio.create_task(_receive(websocket, hub, connection, verified.expires_at)),
        asyncio.create_task(_send(websocket, connection)),
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Also reached when the server is shutting down and this handler is cancelled.
        hub.leave(connection)
        for task in tasks:
            task.cancel()
        # `wait`, not `gather`: it never re-raises what the tasks ended with, and if this handler
        # is itself being cancelled it passes that on unchanged.
        await asyncio.wait(tasks)

    # A task that ended with an error means the phone hung up: there is nobody to close for.
    # (Reading a task's error also marks it as handled, so asyncio doesn't log it later.)
    errors = [task.exception() for task in tasks if not task.cancelled()]
    if not any(errors):
        with suppress(Exception):
            await websocket.close(next(iter(done)).result())
