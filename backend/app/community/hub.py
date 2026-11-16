"""Who is connected to the live chat right now, and how a new message reaches them.

Everything here lives in the memory of the one server process, so it only works with ONE process
(the Dockerfile starts one, and Render's free plan runs one). With more than one, a message
posted on one would not be pushed to the phones connected to another. Nothing would be lost,
because every phone also asks "anything new?" on a timer (see the app's sync), but it would
arrive up to that timer late.

A phone that can't keep up must never slow the others down: each connection has its own bounded
queue, `publish` never waits, and a connection whose queue fills is dropped. The phone then
reconnects and catches up over HTTP.
"""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

# Close codes in the range WebSocket leaves to applications (4000-4999).
CLOSE_BAD_REQUEST = 4400
CLOSE_UNAUTHORIZED = 4401  # no login, a bad one, or it ran out: the phone signs in again
CLOSE_IDLE = 4408  # nothing heard from the phone for too long
CLOSE_REPLACED = 4409  # the same person connected from too many places
CLOSE_TOO_SLOW = 4429  # the phone wasn't reading; it reconnects and catches up
CLOSE_TRY_LATER = 1013  # full, or sign-in can't be checked right now

QUEUE_SIZE = 200
PER_USER = 3  # a phone that reconnects can briefly hold two


class HubFull(Exception):
    pass


@dataclass(eq=False)
class Connection:
    user_id: UUID
    queue: asyncio.Queue[str | None] = field(default_factory=lambda: asyncio.Queue(QUEUE_SIZE))
    close_code: int | None = None


class Hub:
    def __init__(self, max_connections: int = 200, per_user: int = PER_USER) -> None:
        self.max_connections = max_connections
        self.per_user = per_user
        # Insertion ordered, so the first entry for a person is their oldest connection.
        self._by_user: defaultdict[UUID, list[Connection]] = defaultdict(list)
        self._count = 0

    @property
    def online(self) -> int:
        """People connected (someone on two phones counts once)."""
        return len(self._by_user)

    @property
    def connections(self) -> int:
        return self._count

    def join(self, user_id: UUID) -> Connection:
        mine = self._by_user.get(user_id, [])
        if len(mine) >= self.per_user:
            self.drop(mine[0], CLOSE_REPLACED)
        if self._count >= self.max_connections:
            raise HubFull
        newcomer = user_id not in self._by_user
        connection = Connection(user_id)
        self._by_user[user_id].append(connection)
        self._count += 1
        if newcomer:
            self._announce_presence(skip=connection)  # the newcomer is told in its "ready"
        return connection

    def leave(self, connection: Connection) -> None:
        mine = self._by_user.get(connection.user_id)
        if not mine or connection not in mine:
            return  # already gone
        mine.remove(connection)
        self._count -= 1
        if not mine:
            del self._by_user[connection.user_id]
            self._announce_presence()

    def drop(self, connection: Connection, code: int) -> None:
        """Removes a connection and tells its writer to close the socket with `code`."""
        self.leave(connection)
        connection.close_code = code
        # Whatever was waiting to be sent no longer matters; make room for the "close" marker.
        while not connection.queue.empty():
            connection.queue.get_nowait()
        connection.queue.put_nowait(None)

    def send(self, connection: Connection, event: dict[str, Any]) -> None:
        self._offer(connection, json.dumps(event))

    def publish(self, event: dict[str, Any]) -> None:
        """Queues an event for everyone. Never waits, whatever state the phones are in."""
        self._broadcast(json.dumps(event))

    def _broadcast(self, text: str, skip: Connection | None = None) -> None:
        # Copied first: dropping a slow connection changes the lists being walked.
        for connection in [c for mine in self._by_user.values() for c in mine]:
            if connection is not skip:
                self._offer(connection, text)

    def _offer(self, connection: Connection, text: str) -> None:
        if connection.close_code is not None:
            return
        try:
            connection.queue.put_nowait(text)
        except asyncio.QueueFull:
            self.drop(connection, CLOSE_TOO_SLOW)

    def _announce_presence(self, skip: Connection | None = None) -> None:
        self._broadcast(json.dumps({"type": "presence", "online": self.online}), skip)
