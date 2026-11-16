import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from app.community import hub as hub_module
from app.community.hub import Connection, Hub, HubFull
from app.community.router import get_token_verifier
from app.core.auth import CurrentUser, SignInServiceDown, TokenRejected, VerifiedToken
from app.main import app
from tests.conftest import SwitchUser
from tests.test_community_api import delete, fresh_chat, join, post

__all__ = ["fresh_chat"]  # the fixture: a new, empty hub for every test

ALI = uuid.uuid4()
SARA = uuid.uuid4()


def fake_verify(token: str) -> VerifiedToken:
    """Tokens in these tests: "user:<id>", "expired:<id>", "down", anything else is rejected."""
    kind, _, value = token.partition(":")
    if kind == "down":
        raise SignInServiceDown
    if kind not in {"user", "expired"}:
        raise TokenRejected("Invalid or expired token")
    expires = time.time() + (3600 if kind == "user" else -1)
    return VerifiedToken(CurrentUser(id=uuid.UUID(value), email=None), int(expires))


@pytest.fixture(autouse=True)
def fake_tokens() -> Iterator[None]:
    app.dependency_overrides[get_token_verifier] = lambda: fake_verify
    yield
    app.dependency_overrides.pop(get_token_verifier, None)


def sign_in(ws: WebSocketTestSession, user_id: uuid.UUID) -> Any:
    ws.send_json({"type": "auth", "token": f"user:{user_id}"})
    return ws.receive_json()


def closed_with(ws: WebSocketTestSession) -> int:
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    return closed.value.code


# --- Getting in ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("first_frame", "code"),
    [
        ('{"type": "auth", "token": "nonsense"}', hub_module.CLOSE_UNAUTHORIZED),
        ('{"type": "auth", "token": "down"}', hub_module.CLOSE_TRY_LATER),
        ('{"type": "auth"}', hub_module.CLOSE_BAD_REQUEST),
        ('{"type": "ping"}', hub_module.CLOSE_BAD_REQUEST),
        ("not json", hub_module.CLOSE_BAD_REQUEST),
        ('"auth"', hub_module.CLOSE_BAD_REQUEST),
        ('{"type": "auth", "token": "' + "x" * 9000 + '"}', hub_module.CLOSE_BAD_REQUEST),
    ],
    ids=["bad-token", "sign-in-down", "no-token", "not-auth", "not-json", "not-object", "huge"],
)
def test_a_socket_that_does_not_sign_in_properly_is_closed(
    client: TestClient, fresh_chat: Hub, first_frame: str, code: int
) -> None:
    with client.websocket_connect("/community/ws") as ws:
        ws.send_text(first_frame)
        assert closed_with(ws) == code
    assert fresh_chat.connections == 0


def test_a_socket_is_closed_when_its_login_runs_out(client: TestClient, fresh_chat: Hub) -> None:
    with client.websocket_connect("/community/ws") as ws:
        ws.send_json({"type": "auth", "token": f"expired:{ALI}"})
        assert ws.receive_json()["type"] == "ready"
        # The phone treats this code as "sign in again", and reconnects with a fresh token.
        assert closed_with(ws) == hub_module.CLOSE_UNAUTHORIZED
    assert fresh_chat.connections == 0


def test_a_full_chat_turns_newcomers_away_politely(client: TestClient, fresh_chat: Hub) -> None:
    fresh_chat.max_connections = 1
    with client.websocket_connect("/community/ws") as first:
        assert sign_in(first, ALI) == {"type": "ready", "online": 1}
        with client.websocket_connect("/community/ws") as second:
            second.send_json({"type": "auth", "token": f"user:{SARA}"})
            assert closed_with(second) == hub_module.CLOSE_TRY_LATER
        first.send_json({"type": "ping"})
        assert first.receive_json() == {"type": "pong"}  # the one who was in is untouched


# --- What a connected phone hears ----------------------------------------------------------------


def test_new_and_deleted_messages_are_pushed_to_everyone_connected(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    with (
        client.websocket_connect("/community/ws") as ali,
        client.websocket_connect("/community/ws") as sara,
    ):
        sign_in(ali, ALI)
        sign_in(sara, SARA)
        assert ali.receive_json() == {"type": "presence", "online": 2}

        posted = post(client, "Hallo zusammen")
        for ws in (ali, sara):  # the author hears it too: it confirms the send
            assert ws.receive_json() == {"type": "message", "message": posted}

        deleted = delete(client, posted["id"])
        for ws in (ali, sara):
            event = ws.receive_json()
            assert event == {"type": "message", "message": deleted}
            assert event["message"]["body"] is None and event["message"]["rev"] > posted["rev"]

        # Nothing is announced for a retry or a second delete: they changed nothing.
        delete(client, posted["id"])
        ali.send_json({"type": "ping"})
        assert ali.receive_json() == {"type": "pong"}


def test_people_here_now_counts_people_not_phones(client: TestClient, fresh_chat: Hub) -> None:
    with client.websocket_connect("/community/ws") as phone:
        assert sign_in(phone, ALI) == {"type": "ready", "online": 1}
        with client.websocket_connect("/community/ws") as tablet:
            assert sign_in(tablet, ALI) == {"type": "ready", "online": 1}  # same person
            with client.websocket_connect("/community/ws") as sara:
                assert sign_in(sara, SARA) == {"type": "ready", "online": 2}
                assert phone.receive_json() == {"type": "presence", "online": 2}
                assert tablet.receive_json() == {"type": "presence", "online": 2}
            assert phone.receive_json() == {"type": "presence", "online": 1}  # Sara left
    assert (fresh_chat.online, fresh_chat.connections) == (0, 0)


def test_anything_the_phone_sends_besides_a_ping_is_ignored(client: TestClient) -> None:
    with client.websocket_connect("/community/ws") as ws:
        sign_in(ws, ALI)
        ws.send_text("garbage")
        ws.send_json({"type": "message", "body": "posting goes through POST, not the socket"})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


# --- The hub itself ------------------------------------------------------------------------------


def drain(connection: Connection) -> list[str | None]:
    items = []
    while not connection.queue.empty():
        items.append(connection.queue.get_nowait())
    return items


async def test_a_phone_that_stops_reading_is_dropped_and_never_holds_up_the_rest() -> None:
    hub = Hub()
    stuck = hub.join(ALI)
    healthy = hub.join(SARA)
    drain(stuck)  # the presence note about Sara

    for n in range(hub_module.QUEUE_SIZE + 50):
        hub.publish({"type": "message", "n": n})  # must never wait or raise
        drain(healthy)  # this phone keeps reading

    assert stuck.close_code == hub_module.CLOSE_TOO_SLOW
    assert drain(stuck) == [None]  # only "close me" is left: the backlog was thrown away
    assert hub.online == 1 and healthy.close_code is None
    hub.publish({"type": "message", "n": "after"})
    assert stuck.queue.empty()  # nothing more is queued for a dropped phone
    assert len(drain(healthy)) == 1


async def test_a_person_on_too_many_phones_loses_the_oldest_connection() -> None:
    hub = Hub(per_user=2)
    first, second = hub.join(ALI), hub.join(ALI)
    third = hub.join(ALI)
    assert first.close_code == hub_module.CLOSE_REPLACED
    assert (second.close_code, third.close_code) == (None, None)
    assert (hub.online, hub.connections) == (1, 2)
    hub.leave(first)  # leaving twice is harmless
    assert hub.connections == 2


async def test_the_hub_refuses_more_connections_than_it_is_set_for() -> None:
    hub = Hub(max_connections=2)
    hub.join(ALI)
    hub.join(SARA)
    with pytest.raises(HubFull):
        hub.join(uuid.uuid4())
    assert hub.connections == 2
