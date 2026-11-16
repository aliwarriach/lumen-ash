"""Looking a word up by an inflected form ("gehst" finds gehen)."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from app.dictionary.models import DictionaryEntry, DictionaryForm
from tests.conftest import SwitchUser


def seed(db: Engine) -> None:
    with db.begin() as conn:
        gehen = conn.execute(
            insert(DictionaryEntry)
            .values(
                source_key="gehen|verb|0|1",
                lemma="gehen",
                lemma_lower="gehen",
                pos="verb",
                genders=[],
                plurals=[],
                plural_only=False,
                meanings=["to go", "to walk"],
                example_de="Ich gehe nach Hause.",
                example_en="I am going home.",
            )
            .returning(DictionaryEntry.id)
        ).scalar_one()
        tisch = conn.execute(
            insert(DictionaryEntry)
            .values(
                source_key="Tisch|noun|0|1",
                lemma="Tisch",
                lemma_lower="tisch",
                pos="noun",
                genders=["m"],
                plurals=["Tische"],
                plural_only=False,
                meanings=["table"],
            )
            .returning(DictionaryEntry.id)
        ).scalar_one()
        conn.execute(
            insert(DictionaryForm),
            [
                {"form_lower": "gehst", "entry_id": gehen},
                {"form_lower": "tische", "entry_id": tisch},
            ],
        )


def test_an_inflected_form_finds_its_word(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed(db)

    body = client.get("/dictionary/lookup", params={"q": "gehst"}).json()

    assert body["matched_form"] == "gehst"
    assert [e["lemma"] for e in body["entries"]] == ["gehen"]
    assert body["entries"][0]["example_de"] == "Ich gehe nach Hause."
    assert body["entries"][0]["example_en"] == "I am going home."


def test_the_form_lookup_ignores_case_and_a_leading_article(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed(db)

    body = client.get("/dictionary/lookup", params={"q": "die Tische"}).json()

    assert [e["lemma"] for e in body["entries"]] == ["Tisch"]
    assert body["matched_form"] == "Tische"


def test_a_headword_is_found_as_itself_with_no_form_note(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    seed(db)

    body = client.get("/dictionary/lookup", params={"q": "gehen"}).json()

    assert [e["lemma"] for e in body["entries"]] == ["gehen"]
    assert body["matched_form"] is None


def test_an_unknown_word_finds_nothing(client: TestClient, as_user: SwitchUser, db: Engine) -> None:
    seed(db)

    body = client.get("/dictionary/lookup", params={"q": "xyzzy"}).json()

    assert body["entries"] == [] and body["matched_form"] is None


def test_a_lowercase_form_prefers_the_lowercase_word_and_a_capital_the_noun(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    with db.begin() as conn:
        ids = {}
        for key, lemma, pos in (
            ("klein|adj|0|1", "klein", "adj"),
            ("Kleiner|noun|0|1", "Kleiner", "noun"),
        ):
            ids[lemma] = conn.execute(
                insert(DictionaryEntry)
                .values(
                    source_key=key,
                    lemma=lemma,
                    lemma_lower=lemma.lower(),
                    pos=pos,
                    genders=[],
                    plurals=[],
                    plural_only=False,
                    meanings=["small"],
                )
                .returning(DictionaryEntry.id)
            ).scalar_one()
        conn.execute(
            insert(DictionaryForm),
            [{"form_lower": "kleine", "entry_id": entry_id} for entry_id in ids.values()],
        )

    lower = client.get("/dictionary/lookup", params={"q": "kleine"}).json()
    capital = client.get("/dictionary/lookup", params={"q": "Kleine"}).json()

    assert [e["lemma"] for e in lower["entries"]] == ["klein", "Kleiner"]
    assert [e["lemma"] for e in capital["entries"]] == ["Kleiner", "klein"]
