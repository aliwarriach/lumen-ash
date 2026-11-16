import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.review import router as review_router
from app.review import service as review_service
from tests.conftest import SwitchUser

TISCH = {
    "kind": "noun",
    "german": "Tisch",
    "article": "der",
    "plural": "Tische",
    "meaning_en": "table",
}
GEHEN = {
    "kind": "verb",
    "german": "gehen",
    "meaning_en": "to go",
    "verb_forms": {"present": {"ich": "gehe", "er_sie_es": "geht"}, "past_participle": "gegangen"},
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Clock]:
    c = Clock()
    monkeypatch.setattr(review_service, "utcnow", lambda: c.now)
    monkeypatch.setattr(review_router, "utcnow", lambda: c.now)
    yield c


def add_word(client: TestClient, body: dict[str, Any] = TISCH) -> dict[str, Any]:
    response = client.post("/words", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def queue(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/reviews/queue", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def card_of(client: TestClient, card_type: str, word_id: str | None = None) -> dict[str, Any]:
    for c in queue(client)["cards"]:
        if c["card_type"] == card_type and (word_id is None or c["word"]["id"] == word_id):
            return c
    raise AssertionError(f"no {card_type} card due")


def answer(
    client: TestClient, card: dict[str, Any], rating: int = 3, status: int = 200, **ans: Any
) -> dict[str, Any]:
    body = {"id": str(uuid.uuid4()), "card_id": card["card_id"], "rating": rating, "answer": ans}
    response = client.post("/reviews", json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_queue_creates_cards_for_each_word(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    add_word(client, GEHEN)
    q = queue(client)
    by_word: dict[str, list[str]] = {}
    for c in q["cards"]:
        by_word.setdefault(c["word"]["german"], []).append(c["card_type"])
    # Recognise first, then article, then produce. No sentence card until Familiar.
    assert by_word == {"Tisch": ["recall", "article", "produce"], "gehen": ["recall", "produce"]}
    assert all(c["is_new"] for c in q["cards"])
    assert q["due_count"] == 0 and q["new_count"] == 5


def test_new_cards_are_limited_per_local_day(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    for i in range(10):
        add_word(client, {**TISCH, "german": f"Tisch{i}"})
    q = queue(client, tz="Asia/Karachi")
    assert len(q["cards"]) == 15 and q["new_count"] == 15

    for c in q["cards"][:2]:  # start two new cards today
        answer(client, c, rating=3, article="der", plural="Tische")
    assert queue(client, tz="Asia/Karachi")["new_count"] == 13

    # The next local day (Karachi midnight = 19:00 UTC) gives a fresh allowance.
    clock.now = datetime(2026, 11, 10, 19, 1, tzinfo=UTC)
    assert queue(client, tz="Asia/Karachi")["new_count"] == 15


def test_wrong_typed_answer_counts_as_again_and_returns_soon(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    produce = card_of(client, "produce")
    result = answer(client, produce, rating=4, text="das Tisch")
    assert result["correct"] is False and result["checked"] is True
    assert result["rating"] == 1  # Easy was overridden
    assert result["expected"] == "der Tisch"
    assert result["feedback"] == "Wrong article: it's der Tisch."
    assert datetime.fromisoformat(result["due"]) <= clock.now + timedelta(minutes=10)
    # Still in today's queue (within the learn-ahead window), now as a due review.
    again = card_of(client, "produce")
    assert again["is_new"] is False


def test_correct_answers_graduate_a_card(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    recall = card_of(client, "recall")
    answer(client, recall, rating=3)
    clock.advance(minutes=10)
    result = answer(client, recall, rating=3)
    assert datetime.fromisoformat(result["due"]) - clock.now >= timedelta(days=1)
    assert all(c["card_type"] != "recall" for c in queue(client)["cards"])


def test_resending_the_same_answer_is_harmless(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    recall = card_of(client, "recall")
    body = {"id": str(uuid.uuid4()), "card_id": recall["card_id"], "rating": 3}
    first = client.post("/reviews", json=body).json()
    second = client.post("/reviews", json=body).json()
    assert first["duplicate"] is False and second["duplicate"] is True
    assert first["due"] == second["due"]

    produce = card_of(client, "produce")
    reused = {**body, "card_id": produce["card_id"]}
    assert client.post("/reviews", json=reused).status_code == 409


def test_offline_answers_keep_their_time_and_a_wrong_phone_clock_never_loses_one(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    word = add_word(client)
    recall = card_of(client, "recall")
    base = {"card_id": recall["card_id"], "rating": 3}

    def post(at: datetime) -> int:
        body = {**base, "id": str(uuid.uuid4()), "reviewed_at": at.isoformat()}
        return client.post("/reviews", json=body).status_code

    def recorded() -> datetime:
        history = client.get(f"/words/{word['id']}/reviews").json()
        return datetime.fromisoformat(history[0]["reviewed_at"])

    assert post(clock.now.replace(tzinfo=None)) == 422  # times must say their timezone

    # Answered on the phone eight days ago, uploaded now: the time it was given is kept.
    assert post(clock.now - timedelta(days=8)) == 200
    assert recorded() == clock.now - timedelta(days=8)

    # A phone whose clock runs ahead, or is set years back: the app would drop a refused answer,
    # so it is accepted and counted as given now.
    for wrong_clock in (timedelta(hours=1), -timedelta(days=2000)):
        clock.advance(minutes=1)
        assert post(clock.now + wrong_clock) == 200
        assert recorded() == clock.now


def test_checked_cards_need_an_answer(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    answer(client, card_of(client, "produce"), status=422)
    article = answer(client, card_of(client, "article"), article="der", plural="Tische")
    assert article["correct"] is True


def test_word_goes_from_new_to_mastered(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    word = add_word(client)
    wid = word["id"]

    def do(card_type: str, **ans: Any) -> dict[str, Any]:
        return answer(client, card_of(client, card_type, wid), rating=3, **ans)

    def stage() -> str:
        return client.get(f"/words/{wid}").json()["stage"]

    # Day 0: two passes through each card's learning steps.
    assert do("recall")["stage"] == "learning"
    do("article", article="der", plural="Tische")
    do("produce", text="der Tisch")
    clock.advance(minutes=10)
    # Recall graduating completes "recognised + produced correctly" -> Familiar.
    result = do("recall")
    assert result["stage"] == "familiar" and result["stage_changed"] is True
    assert "produced it correctly" in result["stage_reason"]
    do("article", article="der", plural="Tische")
    assert do("produce", text="der Tisch")["stage_changed"] is False

    # Familiar unlocks the sentence card, and a sentence must use the word.
    sentence = card_of(client, "sentence", wid)
    answer(client, sentence, status=422, text="Der Stuhl ist neu.")

    # Day 2: the produce card's interval grows past a week -> Usable.
    clock.advance(days=2)
    do("recall")
    do("article", article="der", plural="Tische")
    assert do("produce", text="der Tisch")["stage"] == "usable"

    # Correct sentences on two different days -> Mastered.
    assert do("sentence", text="Der Tisch ist groß.")["stage"] == "usable"
    clock.advance(days=3)
    assert do("sentence", text="Wir kaufen einen Tisch.")["stage"] == "mastered"
    assert stage() == "mastered"

    # A mistake brings it back down.
    clock.advance(days=30)
    assert answer(client, card_of(client, "produce", wid), text="die Tisch")["stage"] == "learning"

    history = client.get(f"/words/{wid}/reviews").json()
    assert history[0]["answer"] == "die Tisch" and history[0]["correct"] is False


def test_noun_becoming_verb_loses_its_article_card(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    word = add_word(client)
    assert any(c["card_type"] == "article" for c in queue(client)["cards"])
    client.patch(f"/words/{word['id']}", json={"kind": "verb", "article": None, "plural": None})
    assert [c["card_type"] for c in queue(client)["cards"]] == ["recall", "produce"]


def test_users_cannot_answer_each_others_cards(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client)
    recall = card_of(client, "recall")
    as_user(uuid.uuid4())
    assert queue(client)["cards"] == []
    answer(client, recall, status=404)


def test_bad_timezone_rejected(client: TestClient, as_user: SwitchUser) -> None:
    assert client.get("/reviews/queue", params={"tz": "Mars/Base"}).status_code == 422
