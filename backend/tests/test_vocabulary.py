import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from app.dictionary.models import DictionaryEntry
from tests.conftest import SwitchUser

TISCH = {"kind": "noun", "german": "Tisch", "article": "der", "meaning_en": "table"}


def add_word(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/words", json={**TISCH, **body})
    assert response.status_code == 201, response.text
    return response.json()


def seed_dictionary(db: Engine) -> None:
    rows: list[dict[str, Any]] = [
        {
            "source_key": "Tisch|noun|0|1",
            "lemma": "Tisch",
            "lemma_lower": "tisch",
            "pos": "noun",
            "genders": ["m"],
            "plurals": ["Tische"],
            "meanings": ["table", "desk"],
            "audio_url": "https://upload.wikimedia.org/x/De-Tisch.ogg.mp3",
        },
        {
            "source_key": "Tischler|noun|0|1",
            "lemma": "Tischler",
            "lemma_lower": "tischler",
            "pos": "noun",
            "genders": ["m"],
            "plurals": ["Tischler"],
            "meanings": ["carpenter"],
        },
        {
            "source_key": "essen|verb|0|1",
            "lemma": "essen",
            "lemma_lower": "essen",
            "pos": "verb",
            "genders": [],
            "plurals": [],
            "meanings": ["to eat"],
            "verb_forms": {"present": {"ich": "esse", "du": "isst"}, "auxiliary": "haben"},
        },
        {
            "source_key": "Essen|noun|1|1",
            "lemma": "Essen",
            "lemma_lower": "essen",
            "pos": "noun",
            "genders": ["n"],
            "plurals": ["Essen"],
            "meanings": ["food", "meal"],
        },
        {
            "source_key": "Eltern|noun|0|1",
            "lemma": "Eltern",
            "lemma_lower": "eltern",
            "pos": "noun",
            "genders": [],
            "plurals": [],
            "plural_only": True,
            "meanings": ["parents"],
        },
    ]
    defaults = {"plural_only": False, "ipa": None, "audio_url": None, "verb_forms": None}
    with db.begin() as conn:
        conn.execute(insert(DictionaryEntry), [{**defaults, **row} for row in rows])


# --- Dictionary lookup ---


def test_lookup_fills_in_article_plural_and_audio(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed_dictionary(db)
    result = client.get("/dictionary/lookup", params={"q": " der Tisch "}).json()

    assert result["query"] == "Tisch"
    [entry] = result["entries"]
    assert entry["kind"] == "noun"
    assert entry["articles"] == ["der"]
    assert entry["plurals"] == ["Tische"]
    assert entry["meanings"] == ["table", "desk"]
    assert entry["wiktionary_url"] == "https://en.wiktionary.org/wiki/Tisch#German"
    assert result["suggestions"] == ["Tischler"]
    assert "Wiktionary" in result["attribution"]


def test_lookup_puts_matching_capitalisation_first(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed_dictionary(db)
    lower = client.get("/dictionary/lookup", params={"q": "essen"}).json()["entries"]
    upper = client.get("/dictionary/lookup", params={"q": "Essen"}).json()["entries"]
    assert [e["kind"] for e in lower] == ["verb", "noun"]
    assert [e["kind"] for e in upper] == ["noun", "verb"]
    assert lower[0]["verb_forms"]["present"]["du"] == "isst"


def test_lookup_plural_only_noun_takes_die(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed_dictionary(db)
    [entry] = client.get("/dictionary/lookup", params={"q": "Eltern"}).json()["entries"]
    assert entry["articles"] == ["die"]
    assert entry["plural_only"] is True


def test_lookup_shows_only_my_saved_copies(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed_dictionary(db)
    me, other, newcomer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    as_user(me)
    mine = add_word(client)
    as_user(other)
    add_word(client)

    as_user(me)
    result = client.get("/dictionary/lookup", params={"q": "TISCH"}).json()
    assert [s["id"] for s in result["saved"]] == [mine["id"]]

    as_user(newcomer)
    assert client.get("/dictionary/lookup", params={"q": "tisch"}).json()["saved"] == []


def test_lookup_escapes_like_wildcards(client: TestClient, as_user: SwitchUser, db: Engine) -> None:
    seed_dictionary(db)
    assert client.get("/dictionary/lookup", params={"q": "%"}).json()["suggestions"] == []
    assert client.get("/dictionary/lookup", params={"q": "T_"}).json()["suggestions"] == []


# --- Words ---


def test_create_noun_and_verb(client: TestClient, as_user: SwitchUser) -> None:
    noun = add_word(client, plural="Tische", audio_url="https://upload.wikimedia.org/a.mp3")
    assert noun["stage"] == "new"
    assert noun["plural"] == "Tische"

    verb = add_word(
        client,
        kind="verb",
        german="aufstehen",
        article=None,
        meaning_en="to get up",
        sentence_pattern="um 7 Uhr aufstehen",
        verb_forms={
            "present": {"ich": "stehe auf", "du": "stehst auf"},
            "past_participle": "aufgestanden",
            "auxiliary": "sein",
            "separable": True,
        },
    )
    assert verb["verb_forms"]["present"]["ich"] == "stehe auf"
    assert verb["verb_forms"]["separable"] is True


def test_kind_specific_fields_are_enforced(client: TestClient, as_user: SwitchUser) -> None:
    bad: list[dict[str, Any]] = [
        {"kind": "verb", "article": "der"},  # verbs have no article
        {"kind": "noun", "verb_forms": {"present": {"ich": "x"}}},  # nouns have no verb forms
        {"plural_only": True, "plural": "Tische"},
        {"plural_only": True, "article": "der"},
        {"audio_url": "http://insecure.example/a.mp3"},
        {"meaning_en": ""},
    ]
    for body in bad:
        response = client.post("/words", json={**TISCH, **body})
        assert response.status_code == 422, body


def test_stage_cannot_be_set_by_hand(client: TestClient, as_user: SwitchUser) -> None:
    word = add_word(client, stage="mastered")
    assert word["stage"] == "new"
    response = client.patch(f"/words/{word['id']}", json={"stage": "mastered"})
    assert response.status_code == 200
    assert response.json()["stage"] == "new"


def test_update_validates_the_merged_word(client: TestClient, as_user: SwitchUser) -> None:
    word = add_word(client)
    # Turning a noun into a verb while it still has an article is rejected...
    assert client.patch(f"/words/{word['id']}", json={"kind": "verb"}).status_code == 422
    # ...but clearing the article at the same time is fine.
    response = client.patch(f"/words/{word['id']}", json={"kind": "verb", "article": None})
    assert response.status_code == 200
    assert response.json()["kind"] == "verb"
    assert client.patch(f"/words/{word['id']}", json={"german": None}).status_code == 422


def test_words_link_to_my_chapters_only(client: TestClient, as_user: SwitchUser) -> None:
    chapter = client.post("/chapters", json={"number": 1, "title": "Kapitel 1"}).json()
    word = add_word(client, chapter_id=chapter["id"])

    listed = client.get("/chapters").json()[0]
    assert listed["words"] == {"total": 1, "mastered": 0}
    assert client.get(f"/chapters/{chapter['id']}").json()["words"]["total"] == 1
    assert [w["id"] for w in client.get("/words", params={"chapter_id": chapter["id"]}).json()] == [
        word["id"]
    ]

    as_user(uuid.uuid4())
    response = client.post("/words", json={**TISCH, "chapter_id": chapter["id"]})
    assert response.status_code == 422


def test_deleting_chapter_keeps_its_words(client: TestClient, as_user: SwitchUser) -> None:
    chapter = client.post("/chapters", json={"number": 1, "title": "Kapitel 1"}).json()
    word = add_word(client, chapter_id=chapter["id"])
    client.delete(f"/chapters/{chapter['id']}")
    assert client.get(f"/words/{word['id']}").json()["chapter_id"] is None


def test_search_words(client: TestClient, as_user: SwitchUser) -> None:
    add_word(client)
    add_word(client, german="Stuhl", meaning_en="chair")
    assert [w["german"] for w in client.get("/words", params={"q": "chai"}).json()] == ["Stuhl"]
    assert [w["german"] for w in client.get("/words", params={"q": "tis"}).json()] == ["Tisch"]
    assert client.get("/words", params={"q": "%"}).json() == []


def test_users_cannot_touch_each_others_words(client: TestClient, as_user: SwitchUser) -> None:
    word = add_word(client)
    as_user(uuid.uuid4())
    assert client.get("/words").json() == []
    assert client.get(f"/words/{word['id']}").status_code == 404
    assert client.patch(f"/words/{word['id']}", json={"german": "x"}).status_code == 404
    assert client.delete(f"/words/{word['id']}").status_code == 404


def test_word_endpoints_require_login(client: TestClient) -> None:
    assert client.get("/words").status_code == 401
    assert client.get("/dictionary/lookup", params={"q": "Tisch"}).status_code == 401
