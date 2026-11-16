import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app import remap_user
from tests.conftest import SwitchUser
from tests.test_course import add_resource, create_chapter
from tests.test_mistakes import ACCUSATIVE
from tests.test_review_api import GEHEN, TISCH

OLD = uuid.uuid4()
NEW = uuid.uuid4()


def fill(client: TestClient) -> None:
    chapter = create_chapter(client, 1)
    add_resource(client, chapter["id"])
    for word in (TISCH, GEHEN):
        assert client.post("/words", json=word).status_code == 201
    assert client.post("/mistakes", json=ACCUSATIVE).status_code == 201
    task = {"items": [{"title": "Seite 24"}]}
    assert client.post("/class-tasks", json=task).status_code == 201


def titles(client: TestClient, path: str, key: str) -> list[Any]:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return [row[key] for row in response.json()]


def test_a_restored_database_is_handed_to_the_new_login_and_the_old_id_sees_nothing(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    as_user(OLD)
    fill(client)
    assert client.get("/dashboard").status_code == 200  # makes review cards, so more tables fill

    with db.begin() as conn:
        moved = remap_user.remap(conn, OLD, NEW)
    assert moved["chapters"] == 1 and moved["vocab_words"] == 2 and moved["class_tasks"] == 1
    assert moved["review_cards"] > 0 and moved["mistakes"] == 1

    as_user(NEW)
    assert titles(client, "/chapters", "title") == ["Kapitel 1"]
    assert titles(client, "/class-tasks", "title") == ["Seite 24"]
    assert len(client.get("/words").json()) == 2
    moved_chapters = {c["id"] for c in client.get("/chapters").json()}
    as_user(OLD)
    # The old login now counts as a brand-new learner: it gets the starter course, none of the
    # moved data.
    assert not moved_chapters & {c["id"] for c in client.get("/chapters").json()}
    assert client.get("/class-tasks").json() == []


def test_it_refuses_to_mix_two_learners_or_to_move_nothing(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    as_user(OLD)
    fill(client)
    as_user(NEW)
    create_chapter(client, 7)

    with db.connect() as conn, pytest.raises(ValueError, match="already has data"):
        remap_user.remap(conn, OLD, NEW)
    with db.connect() as conn, pytest.raises(ValueError, match="no data"):
        remap_user.remap(conn, uuid.uuid4(), uuid.uuid4())
    with db.connect() as conn, pytest.raises(ValueError, match="same"):
        remap_user.remap(conn, OLD, OLD)

    as_user(OLD)  # nothing moved
    assert titles(client, "/chapters", "title") == ["Kapitel 1"]


def test_every_table_that_belongs_to_a_learner_is_covered() -> None:
    """A new table with a user_id column is picked up automatically, so none is left behind."""
    tables = remap_user.user_tables()
    assert {"chapters", "vocab_words", "class_tasks", "exams", "ai_usage", "coach_checks"} <= set(
        tables
    )
    assert "dictionary_entries" not in tables and "ai_cache" not in tables  # shared, not personal
