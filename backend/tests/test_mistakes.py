import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import SwitchUser
from tests.test_review_api import TISCH, Clock, add_word, answer, clock, queue

__all__ = ["clock"]  # the fixture, re-used from the review tests

ACCUSATIVE = {
    "wrong": "Ich habe ein Tisch gekauft.",
    "correct": "Ich habe einen Tisch gekauft.",
    "pattern_key": "accusative",
}


def log(client: TestClient, status: int = 201, **body: Any) -> dict[str, Any]:
    response = client.post("/mistakes", json={**ACCUSATIVE, **body})
    assert response.status_code == status, response.text
    return response.json()


def retry_card(client: TestClient, mistake_id: str) -> dict[str, Any]:
    for c in queue(client)["cards"]:
        if c["card_type"] == "error_retry" and c["mistake"]["id"] == mistake_id:
            return c
    raise AssertionError("no retry card due")


def test_logging_a_mistake_fills_in_the_category_and_links_words(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    tisch = add_word(client, TISCH)
    m = log(client, word_ids=[tisch["id"]], explanation="Tisch is masculine.", source="Homework")
    assert m["category"] == "case"  # from the accusative pattern
    assert m["pattern_title"] == "Accusative case: den, einen"
    assert [w["german"] for w in m["words"]] == ["Tisch"]
    assert m["repeat_of"] is None
    assert m["retry"]["retries"] == 0 and m["retry"]["last_correct"] is None

    assert client.get("/mistakes", params={"word_id": tisch["id"]}).json()[0]["id"] == m["id"]
    assert client.get("/mistakes", params={"category": "article"}).json() == []


def test_mistake_validation(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    log(client, status=422, correct="Ich habe ein Tisch gekauft")  # same as wrong
    log(client, status=422, pattern_key=None)  # needs a category or a pattern
    log(client, status=422, word_ids=[str(uuid.uuid4())])
    log(client, status=422, chapter_id=str(uuid.uuid4()))
    assert log(client, pattern_key=None, category="spelling")["category"] == "spelling"

    m = log(client)
    patch = client.patch(f"/mistakes/{m['id']}", json={"correct": None})
    assert patch.status_code == 422
    same = client.patch(f"/mistakes/{m['id']}", json={"correct": ACCUSATIVE["wrong"]})
    assert same.status_code == 422


def test_retry_card_is_checked_and_shown_without_using_the_new_word_allowance(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(client)
    before = queue(client)["new_count"]
    card = retry_card(client, m["id"])
    assert card["word"] is None and card["is_new"] is True
    assert card["mistake"]["wrong"] == ACCUSATIVE["wrong"]

    wrong = answer(client, card, rating=4, text="Ich habe einen tisch gekauft")
    assert wrong["correct"] is False and wrong["rating"] == 1
    assert wrong["feedback"] == "Check the capital letters."
    assert wrong["mistake_id"] == m["id"] and wrong["stage"] is None

    clock.advance(minutes=2)
    right = answer(client, retry_card(client, m["id"]), text="Ich habe einen Tisch gekauft")
    assert right["correct"] is True
    assert queue(client)["new_count"] == before

    retry = client.get(f"/mistakes/{m['id']}").json()["retry"]
    assert retry == {"due": retry["due"], "retries": 2, "last_correct": True}


def test_word_order_feedback_and_empty_answers(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(
        client,
        wrong="Heute ich lerne Deutsch.",
        correct="Heute lerne ich Deutsch.",
        pattern_key="verb_second",
    )
    card = retry_card(client, m["id"])
    answer(client, card, status=422)
    result = answer(client, card, text="Heute ich lerne Deutsch")
    assert result["feedback"] == "The right words, but in the wrong order."


def test_repeats_are_recognised_with_a_reason(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    tisch = add_word(client, TISCH)
    first = log(client, word_ids=[tisch["id"]])
    clock.advance(days=1)
    same_fix = log(client, wrong="Ich habe einen tisch gekauft.")
    assert same_fix["repeat_of"]["id"] == first["id"]
    assert same_fix["repeat_of"]["reason"] == "Same correction as before."

    clock.advance(days=1)
    same_rule = log(
        client,
        wrong="Ich sehe der Tisch.",
        correct="Ich sehe den Tisch.",
        word_ids=[tisch["id"]],
    )
    assert same_rule["repeat_of"]["id"] == first["id"]
    assert same_rule["repeat_of"]["reason"] == "Accusative case: den, einen again, with Tisch."

    clock.advance(days=1)
    other = log(client, wrong="Ich sehe der Mann.", correct="Ich sehe den Mann.")
    assert other["repeat_of"] is None
    assert [m["id"] for m in client.get("/mistakes", params={"repeats_only": True}).json()] == [
        same_rule["id"],
        same_fix["id"],
    ]

    # Deleting the original leaves the later ones, no longer marked as repeats.
    assert client.delete(f"/mistakes/{first['id']}").status_code == 204
    assert client.get(f"/mistakes/{same_fix['id']}").json()["repeat_of"] is None


def test_summary_groups_mistakes(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    log(client)
    clock.advance(hours=1)
    log(client, wrong="Ich habe ein Tisch gekauft!")  # repeat
    log(client, wrong="Er fahrt.", correct="Er fährt.", pattern_key="stem_change")
    summary = client.get("/mistakes/summary").json()
    assert summary["total"] == 3 and summary["repeats"] == 1
    assert summary["by_category"][0] == {
        "category": "case",
        "total": 2,
        "last_30_days": 2,
        "repeats": 1,
    }
    assert [p["key"] for p in summary["by_pattern"]] == ["accusative", "stem_change"]


def test_deleting_a_mistake_removes_its_card_and_evidence(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(client)
    answer(client, retry_card(client, m["id"]), text="Ich habe einen Tisch gekauft.")
    assert client.get("/grammar/patterns/accusative").json()["stats"]["attempts"] == 2

    assert client.delete(f"/mistakes/{m['id']}").status_code == 204
    assert all(c["card_type"] != "error_retry" for c in queue(client)["cards"])
    assert client.get("/grammar/patterns/accusative").json()["stats"]["attempts"] == 0
    assert client.get(f"/mistakes/{m['id']}").status_code == 404


def test_deleting_a_word_unlinks_it(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    tisch = add_word(client, TISCH)
    m = log(client, word_ids=[tisch["id"]])
    client.delete(f"/words/{tisch['id']}")
    assert client.get(f"/mistakes/{m['id']}").json()["words"] == []


def test_users_only_see_their_own_mistakes(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    tisch = add_word(client, TISCH)
    m = log(client)
    as_user(uuid.uuid4())
    assert client.get("/mistakes").json() == []
    assert client.get(f"/mistakes/{m['id']}").status_code == 404
    assert client.delete(f"/mistakes/{m['id']}").status_code == 404
    log(client, status=422, word_ids=[tisch["id"]])  # someone else's word
    assert client.get("/grammar/patterns/accusative").json()["stats"]["mistakes"] == 0
