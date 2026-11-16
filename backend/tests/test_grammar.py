import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.grammar.catalog import PATTERNS, PatternKey
from app.review.grading import normalize
from tests.conftest import SwitchUser
from tests.test_mistakes import log, retry_card
from tests.test_review_api import TISCH, Clock, add_word, answer, card_of, clock, queue

__all__ = ["clock"]  # the fixture, re-used from the review tests


def test_catalogue_is_complete() -> None:
    assert set(PATTERNS) == set(PatternKey)
    for p in PATTERNS.values():
        assert p.explanation and len(p.examples) >= 2 and p.practice
        for m in p.common_mistakes:
            assert normalize(m.wrong) != normalize(m.correct), m


def pattern(client: TestClient, key: str) -> dict[str, Any]:
    response = client.get(f"/grammar/patterns/{key}")
    assert response.status_code == 200, response.text
    return response.json()


def test_pattern_detail_has_content_and_no_stats_yet(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    p = pattern(client, "accusative")
    assert p["title"] == "Accusative case: den, einen" and p["category"] == "case"
    assert p["examples"][0]["german"] == "Ich habe einen Tisch gekauft."
    assert p["stats"]["accuracy"] is None and p["stats"]["level"] == "not_enough_data"
    assert p["evidence"] == []
    assert client.get("/grammar/patterns/dative_case").status_code == 422
    assert len(client.get("/grammar/patterns").json()) == len(PATTERNS)


def test_article_answers_count_for_gender_and_plural(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client, TISCH)
    answer(client, card_of(client, "article"), article="das", plural="Tische")
    answer(client, card_of(client, "produce"), text="der Tisch")
    answer(client, card_of(client, "produce"), text="der Stuhl")  # wrong word: not gender

    gender = pattern(client, "noun_gender")["stats"]
    assert (gender["attempts"], gender["correct"]) == (2, 1)
    plural = pattern(client, "plural_forms")
    assert (plural["stats"]["attempts"], plural["stats"]["correct"]) == (1, 1)
    latest = pattern(client, "noun_gender")["evidence"]
    assert [e["label"] for e in latest] == ["Typed the German", "Article card"]
    assert latest[1]["given"] == "das · Tische" and latest[1]["correct"] is False


def test_weak_patterns_are_ranked_with_reasons_and_evidence(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    """The phase's done-when: the learner sees their top weak patterns, with evidence."""
    first = log(client)
    clock.advance(days=1)
    log(client, wrong="Ich brauche der Stift.", correct="Ich brauche den Stift.")
    log(client, wrong="Er fahrt.", correct="Er fährt.", pattern_key="stem_change")
    answer(client, retry_card(client, first["id"]), text="Ich habe einen Tisch gekauft.")

    weak = client.get("/grammar/weak").json()
    assert [w["key"] for w in weak] == ["accusative", "stem_change"]
    acc = weak[0]
    assert acc["reason"] == "2 wrong out of 3 in the last 30 days (33% right)."
    assert [e["given"] for e in acc["evidence"]] == [
        "Ich brauche der Stift.",
        "Ich habe ein Tisch gekauft.",
    ]
    assert acc["evidence"][0]["source"] == "mistake"
    assert weak[1]["reason"] == "1 wrong out of 1 in the last 30 days (0% right)."

    # Retrying correctly is real progress: the pattern drops out once it has no misses.
    clock.advance(days=31)
    assert client.get("/grammar/weak").json() == []


def test_accuracy_compares_with_the_previous_30_days(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(client)
    clock.advance(days=35)
    card = retry_card(client, m["id"])
    for _ in range(3):  # answers are accepted whenever they're given, due or not
        answer(client, card, text="Ich habe einen Tisch gekauft.")
        clock.advance(days=1)
    log(client, wrong="Ich sehe der Mann.", correct="Ich sehe den Mann.")
    stats = pattern(client, "accusative")["stats"]
    assert stats["accuracy"] == 0.75 and stats["previous_accuracy"] == 0.0
    assert stats["level"] == "ok" and stats["mistakes"] == 2
    weak = client.get("/grammar/weak").json()[0]
    assert weak["reason"] == "1 wrong out of 4 in the last 30 days (75% right), up from 0%."


def test_changing_a_mistakes_pattern_moves_its_evidence(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(client, wrong="Ich gehe zu der Arzt.", correct="Ich gehe zum Arzt.")
    answer(client, retry_card(client, m["id"]), text="Ich gehe zum Arzt.")
    assert pattern(client, "accusative")["stats"]["attempts"] == 2

    client.patch(f"/mistakes/{m['id']}", json={"pattern_key": "dative_prepositions"})
    assert pattern(client, "accusative")["stats"]["attempts"] == 0
    assert pattern(client, "dative_prepositions")["stats"]["attempts"] == 2

    client.patch(f"/mistakes/{m['id']}", json={"pattern_key": None})
    assert pattern(client, "dative_prepositions")["stats"]["attempts"] == 0
    assert queue(client)["due_count"] >= 0  # the retry card itself stays


def test_linking_patterns_to_chapters(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    ch = client.post("/chapters", json={"number": 3, "title": "Freizeit"}).json()
    linked = client.put("/grammar/patterns/modal_verbs/chapters", json={"chapter_ids": [ch["id"]]})
    assert linked.status_code == 200 and linked.json()["chapter_ids"] == [ch["id"]]
    in_chapter = client.get("/grammar/patterns", params={"chapter_id": ch["id"]}).json()
    assert [p["key"] for p in in_chapter] == ["modal_verbs"]

    unknown = {"chapter_ids": [str(uuid.uuid4())]}
    assert client.put("/grammar/patterns/modal_verbs/chapters", json=unknown).status_code == 422
    client.put("/grammar/patterns/modal_verbs/chapters", json={"chapter_ids": []})
    assert client.get("/grammar/patterns", params={"chapter_id": ch["id"]}).json() == []

    as_user(uuid.uuid4())
    theirs = {"chapter_ids": [ch["id"]]}
    assert client.put("/grammar/patterns/modal_verbs/chapters", json=theirs).status_code == 422
