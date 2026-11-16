"""Thirty people in the chat at once, against a real server.

The other community tests call the app in-process, one request at a time. This one starts the
server for real (uvicorn, real sockets, the same five-connection database pool production uses)
and has thirty people connect and all post at the same moment. It checks what "works with 30
people" has to mean:

- every person receives every message, exactly once, over their socket;
- one person's messages arrive in the order they sent them;
- a phone with no socket, keeping up only by asking "anything after N?", misses nothing, even
  while messages are pouring in (this is what the write lock in service.py is for);
- nobody gets an error, and the server is left with no connections when they leave.

Tokens are faked (a token is just the user id); everything else is the real code path.
"""

import asyncio
import json
import random
import socket
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Annotated

import httpx
import pytest
import uvicorn
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from websockets.asyncio.client import connect

from app.community.hub import Hub
from app.community.router import get_hub, get_rules, get_token_verifier
from app.community.service import CommunityRules
from app.core import database
from app.core.auth import CurrentUser, VerifiedToken, get_current_user
from app.main import app
from tests.conftest import TEST_DATABASE_URL

PEOPLE = 30
MESSAGES_EACH = 10
TOTAL = PEOPLE * MESSAGES_EACH
PATIENCE = 60.0  # seconds before the test gives up waiting; a healthy run takes a few

_bearer = HTTPBearer()


def _user_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    return CurrentUser(id=uuid.UUID(credentials.credentials), email=None)


def _verify(token: str) -> VerifiedToken:
    return VerifiedToken(CurrentUser(id=uuid.UUID(token), email=None), int(time.time()) + 3600)


@dataclass
class Server:
    http: str
    ws: str
    hub: Hub


@pytest.fixture
def server(db: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Server]:
    assert TEST_DATABASE_URL
    # The pool the real server runs with (app/core/database.py), not the tests' NullPool: thirty
    # people sharing five database connections is part of what is being tested.
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)
    monkeypatch.setattr(database, "get_engine", lambda: engine)
    database.get_sessionmaker.cache_clear()

    hub = Hub()
    app.dependency_overrides[get_hub] = lambda: hub
    app.dependency_overrides[get_rules] = lambda: CommunityRules(1000, frozenset())
    app.dependency_overrides[get_current_user] = _user_from_header
    app.dependency_overrides[get_token_verifier] = lambda: _verify

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )

    async def serve() -> None:
        await uvicorn_server.serve()
        await engine.dispose()  # in the loop the connections were opened in

    thread = threading.Thread(target=asyncio.run, args=(serve(),), daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not uvicorn_server.started:
        assert time.time() < deadline and thread.is_alive(), "the server did not start"
        time.sleep(0.02)
    try:
        yield Server(f"http://127.0.0.1:{port}", f"ws://127.0.0.1:{port}/community/ws", hub)
    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=15)
        for dep in (get_hub, get_rules, get_current_user, get_token_verifier):
            app.dependency_overrides.pop(dep, None)
        database.get_sessionmaker.cache_clear()  # the next test builds its own again


@dataclass
class Person:
    number: int
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    sent: list[str] = field(default_factory=list)  # ids, in the order they were posted
    heard: list[dict[str, object]] = field(default_factory=list)  # messages off the socket
    statuses: list[int] = field(default_factory=list)


async def take_part(
    person: Person, server: Server, everyone_in: asyncio.Barrier, rng: random.Random
) -> None:
    headers = {"Authorization": f"Bearer {person.user_id}"}
    async with httpx.AsyncClient(base_url=server.http, headers=headers, timeout=PATIENCE) as http:
        named = await http.put("/community/me", json={"display_name": f"Person_{person.number}"})
        person.statuses.append(named.status_code)

        async with connect(server.ws) as ws:
            await ws.send(json.dumps({"type": "auth", "token": str(person.user_id)}))
            assert json.loads(await ws.recv())["type"] == "ready"
            await everyone_in.wait()  # nobody posts until all thirty are connected

            async def listen() -> None:
                while len(person.heard) < TOTAL:
                    event = json.loads(await ws.recv())
                    if event["type"] == "message":
                        person.heard.append(event["message"])

            listening = asyncio.create_task(listen())
            for n in range(MESSAGES_EACH):
                message_id = str(uuid.uuid4())
                person.sent.append(message_id)
                body = {"id": message_id, "body": f"{person.number}: Nachricht {n}"}
                response = await http.post("/community/messages", json=body)
                person.statuses.append(response.status_code)
                await asyncio.sleep(rng.uniform(0, 0.02))  # thirty people typing over each other
            await asyncio.wait_for(listening, PATIENCE)


async def keep_up_by_asking(server: Server, done: asyncio.Event) -> tuple[list[str], list[int]]:
    """A phone with no socket: only GET /community/changes, as fast as it can."""
    headers = {"Authorization": f"Bearer {uuid.uuid4()}"}
    seen: list[str] = []
    cursors = [0]
    async with httpx.AsyncClient(base_url=server.http, headers=headers, timeout=PATIENCE) as http:
        while True:
            last_round = done.is_set()
            response = await http.get("/community/changes", params={"after": cursors[-1]})
            assert response.status_code == 200, response.text
            got = response.json()
            seen += [m["id"] for m in got["items"]]
            cursors.append(got["rev"])
            if last_round and not got["has_more"]:
                return seen, cursors


async def chat(server: Server) -> tuple[list[Person], list[str], list[int], float]:
    rng = random.Random(1636)
    people = [Person(n) for n in range(PEOPLE)]
    everyone_in = asyncio.Barrier(PEOPLE)
    done = asyncio.Event()
    asker = asyncio.create_task(keep_up_by_asking(server, done))
    started = time.perf_counter()
    await asyncio.wait_for(
        asyncio.gather(*(take_part(p, server, everyone_in, rng) for p in people)), PATIENCE
    )
    took = time.perf_counter() - started
    done.set()
    seen, cursors = await asyncio.wait_for(asker, PATIENCE)
    return people, seen, cursors, took


def test_thirty_people_talking_at_once_all_see_everything_once_and_in_order(
    server: Server,
) -> None:
    people, asked, cursors, took = asyncio.run(chat(server))
    everything = {message_id for p in people for message_id in p.sent}
    assert len(everything) == TOTAL

    # Nobody got an error.
    for p in people:
        assert p.statuses == [200] + [201] * MESSAGES_EACH, f"person {p.number}: {p.statuses}"

    for listener in people:
        heard_ids = [str(m["id"]) for m in listener.heard]
        # Every message, exactly once.
        assert len(heard_ids) == TOTAL, f"person {listener.number} heard {len(heard_ids)}"
        assert set(heard_ids) == everything
        # Each person's messages in the order that person sent them.
        for author in people:
            theirs = [i for i in heard_ids if i in set(author.sent)]
            assert theirs == author.sent, f"{listener.number} heard {author.number} out of order"
        # And in the order the conversation is stored in, so every phone shows the same thing.
        seqs = [int(str(m["seq"])) for m in listener.heard]
        assert seqs == sorted(seqs), f"person {listener.number} heard the conversation shuffled"

    # The phone without a socket saw each message once and missed none, though it was asking
    # while messages were still being written.
    assert len(asked) == TOTAL and set(asked) == everything
    assert cursors == sorted(cursors)

    # Everyone has left: nothing is still held on the server.
    deadline = time.time() + 5
    while server.hub.connections and time.time() < deadline:
        time.sleep(0.05)
    assert (server.hub.connections, server.hub.online) == (0, 0)

    print(f"\n{PEOPLE} people, {TOTAL} messages, {TOTAL * PEOPLE} deliveries in {took:.2f}s")
