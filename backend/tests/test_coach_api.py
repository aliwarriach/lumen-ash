import uuid
from collections.abc import Iterator
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, text

from app.ai.deps import get_limits, get_providers
from app.ai.providers import AiProvider
from app.coach.deps import get_languagetool
from app.coach.languagetool import LanguageToolUnavailable, LtMatch
from app.core.database import get_engine
from app.main import app
from tests.conftest import SwitchUser
from tests.test_ai_gateway import FakeProvider
from tests.test_review_api import TISCH, Clock, add_word, clock, queue

__all__ = ["clock"]  # the fixture, re-used from the review tests

SENTENCE = "Ich habe ein Tisch gekauft."
AI_ANSWER = {
    "explanation": "Tisch is masculine. After 'haben' it needs einen.",
    "issues": [],
    "practice": ["Ich sehe einen Hund.", "Er kauft einen Stuhl."],
}


class FakeLanguageTool:
    """Stands in for LanguageTool: returns the matches it was given, or is down."""

    def __init__(self, *matches: LtMatch, down: bool = False) -> None:
        self.matches = list(matches)
        self.down = down
        self.texts: list[str] = []

    async def check(self, text: str) -> list[LtMatch]:
        self.texts.append(text)
        if self.down:
            raise LanguageToolUnavailable("down")
        return self.matches


def accusative_match(text: str = SENTENCE) -> LtMatch:
    start = text.index("ein Tisch")
    return LtMatch(
        start, start + 9, "OBJECT_AGREEMENT", "GRAMMAR", "Akkusativ?", ("einen Tisch",), 0.15
    )


def setup(languagetool: FakeLanguageTool | None, *providers: AiProvider) -> None:
    app.dependency_overrides[get_languagetool] = lambda: languagetool
    app.dependency_overrides[get_providers] = lambda: providers
    app.dependency_overrides[get_limits] = lambda: replace(
        get_limits(), burst_per_minute=1000, user_requests=1000
    )


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    for dep in (get_languagetool, get_providers, get_limits):
        app.dependency_overrides.pop(dep, None)


def add_dictionary(db: Engine) -> None:
    """Tisch (m), Haus (n), Bruder (m) and the verb gehen, as the importer would store them."""
    rows = [
        ("Tisch|noun", "Tisch", "noun", ["m"], ["Tische"], None),
        ("Haus|noun", "Haus", "noun", ["n"], ["Häuser"], None),
        (
            "gehen|verb",
            "gehen",
            "verb",
            [],
            [],
            '{"present": {"ich": "gehe", "du": "gehst", "er_sie_es": "geht"}}',
        ),
    ]
    with db.begin() as conn:
        for key, lemma, pos, genders, plurals, verb_forms in rows:
            conn.execute(
                text(
                    "INSERT INTO dictionary_entries (source_key, lemma, lemma_lower, pos, genders,"
                    " plurals, plural_only, meanings, verb_forms) VALUES (:k, :l, :ll, :p,"
                    " :g, :pl, false, ARRAY['x'], CAST(:vf AS jsonb))"
                ),
                {
                    "k": key,
                    "l": lemma,
                    "ll": lemma.lower(),
                    "p": pos,
                    "g": genders,
                    "pl": plurals,
                    "vf": verb_forms,
                },
            )


def check(
    client: TestClient, body: str = SENTENCE, status: int = 201, **extra: Any
) -> dict[str, Any]:
    response = client.post("/coach/check", json={"text": body, **extra})
    assert response.status_code == status, response.text
    return response.json()


def decide(client: TestClient, correction_id: str, decision: str, status: int = 200) -> Any:
    response = client.post(f"/coach/corrections/{correction_id}/{decision}")
    assert response.status_code == status, response.text
    return response.json()


# --- The Phase 6 example ---------------------------------------------------------------------


def test_ich_habe_ein_tisch_gekauft_gives_a_confirmed_accusative_correction_with_an_explanation(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    lt = FakeLanguageTool(accusative_match())
    setup(lt, FakeProvider("gemini", AI_ANSWER))

    result = check(client)

    (c,) = result["corrections"]
    assert (c["wrong"], c["correct"]) == ("ein Tisch", "einen Tisch")
    assert c["label"] == "confirmed" and c["warning"] is None
    assert c["pattern_key"] == "accusative" and c["pattern_title"] == "Accusative case: den, einen"
    assert c["category"] == "case"
    assert c["sources"] == ["languagetool", "rules"]
    assert "Tisch is masculine (der Tisch)" in c["explanation"]
    assert "accusative" in c["explanation"]
    assert c["status"] == "pending" and c["mistake_id"] is None
    assert result["suggested_text"] == "Ich habe einen Tisch gekauft."
    assert result["checked_by"] == ["languagetool", "ai"] and result["ai_status"] == "ok"
    assert result["explanation"] == AI_ANSWER["explanation"]
    assert result["practice"] == AI_ANSWER["practice"] and result["practice_source"] == "ai"
    assert result["sentence_count"] == 1 and result["redacted"] is False
    # Checking never touches the mistake log by itself.
    assert client.get("/mistakes").json() == []


def test_without_the_dictionary_nothing_is_confirmed(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    (c,) = check(client)["corrections"]
    # LanguageTool's own confidence is low (0.15) and our rules can't back it: be honest.
    assert c["label"] == "uncertain"
    assert c["warning"] == "Verify with your teacher."
    assert c["sources"] == ["languagetool"]


# --- Accept, reject, flag ---------------------------------------------------------------------


def test_accepting_a_correction_logs_the_mistake_with_a_retry_card(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    add_dictionary(db)
    tisch = add_word(client, TISCH)
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    (c,) = check(client)["corrections"]

    accepted = decide(client, c["id"], "accept")
    assert accepted["status"] == "accepted" and accepted["mistake_id"]

    (mistake,) = client.get("/mistakes").json()
    assert mistake["id"] == accepted["mistake_id"]
    assert (mistake["wrong"], mistake["correct"]) == (SENTENCE, "Ich habe einen Tisch gekauft.")
    assert mistake["pattern_key"] == "accusative" and mistake["category"] == "case"
    assert mistake["source"] == "Sentence coach"
    assert "masculine" in mistake["explanation"]
    assert [w["id"] for w in mistake["words"]] == [tisch["id"]]  # the learner's own word
    assert any(
        k["card_type"] == "error_retry" and k["mistake"]["id"] == mistake["id"]
        for k in queue(client)["cards"]
    )

    # Deciding the same way again changes nothing; deciding the other way is refused.
    assert decide(client, c["id"], "accept")["mistake_id"] == mistake["id"]
    assert len(client.get("/mistakes").json()) == 1
    decide(client, c["id"], "reject", status=409)
    decide(client, c["id"], "flag", status=409)


def test_an_accepted_mistake_counts_towards_the_grammar_tracker(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    add_dictionary(db)
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    (c,) = check(client)["corrections"]
    decide(client, c["id"], "accept")
    summary = client.get("/mistakes/summary").json()
    assert [(p["key"], p["total"]) for p in summary["by_pattern"]] == [("accusative", 1)]


def test_rejecting_logs_nothing_and_flagging_keeps_it_for_the_teacher(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    setup(
        FakeLanguageTool(accusative_match()),
        FakeProvider("gemini", AI_ANSWER, {**AI_ANSWER, "explanation": "Again."}),
    )
    first = check(client)["corrections"][0]
    second = check(client, "Ich habe ein Tisch gekauft!")["corrections"][0]

    assert decide(client, first["id"], "reject")["status"] == "rejected"
    assert decide(client, second["id"], "flag")["status"] == "flagged"
    assert client.get("/mistakes").json() == []
    assert [f["id"] for f in client.get("/coach/flagged").json()] == [second["id"]]
    assert client.get("/coach/flagged").json()[0]["sentence_correct"] == (
        "Ich habe einen Tisch gekauft!"
    )

    # After asking the teacher, a flagged correction can still be accepted.
    assert decide(client, second["id"], "accept")["status"] == "accepted"
    assert client.get("/coach/flagged").json() == []
    assert len(client.get("/mistakes").json()) == 1
    decide(client, first["id"], "accept", status=409)  # a rejected one stays rejected


# --- When a checker is missing ---------------------------------------------------------------


def test_a_typo_gets_an_english_explanation_not_languagetools_german_one(
    client: TestClient, as_user: SwitchUser
) -> None:
    typo = LtMatch(14, 18, "GERMAN_SPELLER_RULE", "TYPOS", "Möglicher Tippfehler", ("Hund",), 0.55)
    setup(FakeLanguageTool(typo), FakeProvider("gemini", AI_ANSWER))
    (c,) = check(client, "Ich habe eine Hunt.")["corrections"]
    assert (c["wrong"], c["correct"], c["label"], c["category"]) == (
        "Hunt",
        "Hund",
        "likely",
        "spelling",
    )
    assert c["pattern_key"] is None
    assert c["explanation"] == "Possible spelling mistake: check how 'Hunt' is spelled."


def test_if_the_ai_is_unavailable_languagetool_and_our_rules_still_check(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    setup(FakeLanguageTool(accusative_match()))  # no AI provider at all

    result = check(client)
    (c,) = result["corrections"]
    assert c["label"] == "confirmed" and "masculine" in c["explanation"]
    assert result["checked_by"] == ["languagetool"]
    assert result["ai_status"] == "unavailable" and "isn't available" in result["ai_message"]
    assert result["explanation"] is None
    # Practice comes from our own grammar catalog instead.
    assert result["practice_source"] == "catalog" and result["practice"]
    assert any("accusative" in p.lower() or "Ich" in p for p in result["practice"])


def test_if_the_learner_is_over_their_ai_limit_the_rest_still_works(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    app.dependency_overrides[get_limits] = lambda: replace(
        get_limits(), burst_per_minute=1000, user_requests=0
    )
    result = check(client)
    assert result["ai_status"] == "limit" and "today" in result["ai_message"]
    assert result["corrections"][0]["label"] == "confirmed"


def test_if_languagetool_is_down_the_ai_alone_gives_likely_corrections(
    client: TestClient, as_user: SwitchUser
) -> None:
    ai = {
        "explanation": "The verb must be second.",
        "issues": [
            {
                "wrong": "Heute ich lerne",
                "correct": "Heute lerne ich",
                "topic": "verb_second",
                "why": "The verb comes second.",
            },
            {"wrong": "nicht im Text", "correct": "erfunden"},  # made up: must be dropped
        ],
        "practice": ["Morgen arbeite ich."],
    }
    setup(FakeLanguageTool(down=True), FakeProvider("gemini", ai))
    result = check(client, "Heute ich lerne Deutsch.")

    (c,) = result["corrections"]
    assert (c["label"], c["sources"], c["pattern_key"]) == ("likely", ["ai"], "verb_second")
    assert c["explanation"] == "The verb comes second."
    assert result["checked_by"] == ["ai"]
    assert result["suggested_text"] == "Heute lerne ich Deutsch."


def test_if_nothing_can_check_the_learner_is_told_and_nothing_is_saved(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(FakeLanguageTool(down=True))  # no AI either
    response = client.post("/coach/check", json={"text": SENTENCE})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "unavailable"
    assert client.get("/coach/checks").json() == []  # never "no mistakes found"

    setup(None, FakeProvider("gemini", AI_ANSWER))  # LanguageTool switched off entirely
    assert check(client)["checked_by"] == ["ai"]


def test_the_learner_out_of_ai_with_languagetool_down_gets_the_limit_message(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(FakeLanguageTool(down=True), FakeProvider("gemini", AI_ANSWER))
    app.dependency_overrides[get_limits] = lambda: replace(
        get_limits(), burst_per_minute=1000, user_requests=0
    )
    response = client.post("/coach/check", json={"text": SENTENCE})
    assert (response.status_code, response.json()["detail"]["code"]) == (429, "daily_limit")


# --- Privacy ---------------------------------------------------------------------------------


def test_personal_details_never_reach_languagetool_the_ai_or_the_database(
    client: TestClient, as_user: SwitchUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.coach.router.get_settings", lambda: SimpleNamespace(redact_names=["Sara"])
    )
    lt = FakeLanguageTool()
    provider = FakeProvider("gemini", {**AI_ANSWER, "practice": []})
    setup(lt, provider)

    result = check(client, "Ich rufe Sara an: +92 300 1234567.")

    assert result["redacted"] is True and result["text"] == "Ich rufe [name] an: [phone]."
    assert lt.texts == ["Ich rufe [name] an: [phone]."]
    assert "1234567" not in provider.requests[0].user and "Sara" not in provider.requests[0].user
    stored = client.get("/coach/checks").text
    assert "1234567" not in stored and "Sara" not in stored


# --- Checking more than one sentence ---------------------------------------------------------


def test_each_correction_carries_its_own_sentence(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    text = "Ich bin Ali. Ich habe ein Tisch gekauft. Er geht nach Hause."
    setup(FakeLanguageTool(accusative_match(text)), FakeProvider("gemini", AI_ANSWER))
    result = check(client, text)
    (c,) = result["corrections"]
    assert (c["sentence_wrong"], c["sentence_correct"]) == (
        "Ich habe ein Tisch gekauft.",
        "Ich habe einen Tisch gekauft.",
    )
    assert result["sentence_count"] == 3
    assert (
        result["suggested_text"] == "Ich bin Ali. Ich habe einen Tisch gekauft. Er geht nach Hause."
    )


def test_a_text_with_no_mistakes_says_so_without_inventing_any(
    client: TestClient, as_user: SwitchUser
) -> None:
    ai = {"explanation": "No errors found.", "issues": [], "practice": []}
    setup(FakeLanguageTool(), FakeProvider("gemini", ai))
    result = check(client, "Ich habe einen Tisch gekauft.")
    assert result["corrections"] == [] and result["suggested_text"] is None
    assert result["checked_by"] == ["languagetool", "ai"]
    assert result["explanation"] == "No errors found."


# --- Checking what the AI says ---------------------------------------------------------------


class ScriptedLanguageTool(FakeLanguageTool):
    """Answers each call from a script: the first check of the text, then the re-check."""

    def __init__(self, *answers: list[LtMatch]) -> None:
        super().__init__()
        self.answers = list(answers)

    async def check(self, text: str) -> list[LtMatch]:
        self.texts.append(text)
        return self.answers.pop(0) if self.answers else []


VERB_SECOND = {
    "wrong": "Heute ich lerne",
    "correct": "Heute lerne ich",
    "topic": "verb_second",
    "why": "The verb comes second.",
}


def test_no_errors_found_is_never_shown_next_to_a_correction(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    # Seen live: the AI explains only its own findings, so when LanguageTool found the error it
    # wrote "No errors found." above the correction.
    add_dictionary(db)
    ai = {**AI_ANSWER, "explanation": "No errors found."}
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", ai))

    result = check(client)

    assert len(result["corrections"]) == 1
    assert result["explanation"] is None
    assert result["corrections"][0]["explanation"]  # the correction still explains itself


def test_an_ai_correction_is_sent_back_through_languagetool_with_the_fix_applied(
    client: TestClient, as_user: SwitchUser
) -> None:
    languagetool = ScriptedLanguageTool([], [])  # nothing found, then no objection to the fix
    setup(languagetool, FakeProvider("gemini", {**AI_ANSWER, "issues": [VERB_SECOND]}))

    result = check(client, "Ich bin müde. Heute ich lerne Deutsch.")

    # The second request holds only the corrected sentence, not the whole text.
    assert languagetool.texts == [
        "Ich bin müde. Heute ich lerne Deutsch.",
        "Heute lerne ich Deutsch.",
    ]
    (c,) = result["corrections"]
    assert (c["label"], c["sources"], c["warning"]) == ("likely", ["ai"], None)
    assert result["suggested_text"] == "Ich bin müde. Heute lerne ich Deutsch."


def test_an_ai_correction_languagetool_objects_to_is_uncertain_and_not_applied(
    client: TestClient, as_user: SwitchUser
) -> None:
    bad_fix = {"wrong": "mit der Bus", "correct": "mit den Bus", "topic": "dative_prepositions"}
    # The objection is to "den Bus", inside the words the AI wrote.
    objection = LtMatch(14, 21, "DE_AGREEMENT", "GRAMMAR", "Kasus?", ("dem Bus",), None)
    languagetool = ScriptedLanguageTool([], [objection])
    setup(languagetool, FakeProvider("gemini", {**AI_ANSWER, "issues": [bad_fix]}))

    result = check(client, "Ich fahre mit der Bus.")

    assert languagetool.texts[1] == "Ich fahre mit den Bus."
    (c,) = result["corrections"]
    assert (c["label"], c["warning"]) == ("uncertain", "Verify with your teacher.")
    assert result["suggested_text"] is None  # an uncertain fix is never applied


def test_an_objection_elsewhere_in_the_sentence_does_not_count_against_the_fix(
    client: TestClient, as_user: SwitchUser
) -> None:
    elsewhere = LtMatch(0, 3, "SOME_RULE", "GRAMMAR", "?", ("Wir",), None)  # about "Ich"
    bus = {"wrong": "mit der Bus", "correct": "mit dem Bus", "topic": "dative_prepositions"}
    setup(
        ScriptedLanguageTool([], [elsewhere]),
        FakeProvider("gemini", {**AI_ANSWER, "issues": [bus]}),
    )
    (c,) = check(client, "Ich fahre mit der Bus.")["corrections"]
    assert c["label"] == "likely"


def test_a_fix_that_cannot_be_put_into_the_sentence_is_dropped(
    client: TestClient, as_user: SwitchUser
) -> None:
    # Seen live: "aufstehe" -> "stehe ... auf". Applied, it reads "Ich stehe ... auf um 6 Uhr."
    dots = {"wrong": "aufstehe", "correct": "stehe ... auf", "topic": "separable_verbs"}
    setup(FakeLanguageTool(), FakeProvider("gemini", {**AI_ANSWER, "issues": [dots]}))

    result = check(client, "Ich aufstehe um 6 Uhr.")

    assert result["corrections"] == [] and result["suggested_text"] is None


# --- Writing tasks ---------------------------------------------------------------------------


def test_a_writing_task_is_done_once_a_check_has_enough_sentences(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))
    task = client.post(
        "/coach/tasks", json={"prompt": "5 sentences about your day", "min_sentences": 5}
    ).json()
    assert (task["done"], task["checks"]) == (False, 0)

    short = check(client, "Ich stehe auf. Ich esse.", task_id=task["id"])
    assert (short["task_id"], short["task_done"], short["sentence_count"]) == (task["id"], False, 2)

    full = check(
        client,
        "Ich stehe um sieben auf. Ich frühstücke. Ich fahre zum Kurs. Ich lerne. Ich schlafe.",
        task_id=task["id"],
    )
    assert (full["sentence_count"], full["task_done"]) == (5, True)

    (listed,) = client.get("/coach/tasks").json()
    assert (listed["done"], listed["checks"]) == (True, 2)

    # Deleting the task keeps the checks.
    assert client.delete(f"/coach/tasks/{task['id']}").status_code == 204
    assert client.get("/coach/tasks").json() == []
    assert len(client.get("/coach/checks").json()) == 2


def test_the_list_of_checks_matches_each_check_and_costs_three_queries(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    task = client.post("/coach/tasks", json={"prompt": "Your day", "min_sentences": 1}).json()
    made = [check(client), check(client, task_id=task["id"]), check(client)]

    selects: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        listed = client.get("/coach/checks").json()
    finally:
        event.remove(engine, "before_cursor_execute", count)

    # The checks, all their corrections, their tasks: not one query per check.
    assert len(selects) == 3, selects
    assert {c["id"]: c for c in listed} == {c["id"]: c for c in made}
    assert [c["task_done"] for c in listed if c["task_id"]] == [True]
    assert all(len(c["corrections"]) == 1 for c in listed)


def test_task_and_text_validation(client: TestClient, as_user: SwitchUser) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))
    assert client.post("/coach/tasks", json={"prompt": " "}).status_code == 422
    assert client.post("/coach/tasks", json={"prompt": "x", "min_sentences": 0}).status_code == 422
    check(client, "   ", status=422)
    check(client, "Wort " * 200, status=422)  # over the 600 character limit
    check(client, task_id=str(uuid.uuid4()), status=404)  # not a task of theirs


# --- Privacy between learners ----------------------------------------------------------------


def test_one_learner_cannot_see_or_decide_anothers_work(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_dictionary(db)
    setup(FakeLanguageTool(accusative_match()), FakeProvider("gemini", AI_ANSWER))
    alice, bob = uuid.uuid4(), uuid.uuid4()
    as_user(alice)
    result = check(client)
    correction = result["corrections"][0]["id"]
    task = client.post("/coach/tasks", json={"prompt": "Mine"}).json()

    as_user(bob)
    assert client.get(f"/coach/checks/{result['id']}").status_code == 404
    assert client.get("/coach/checks").json() == []
    assert client.post(f"/coach/corrections/{correction}/accept").status_code == 404
    assert client.get("/coach/tasks").json() == []
    assert client.delete(f"/coach/tasks/{task['id']}").status_code == 404
    check(client, task_id=task["id"], status=404)

    as_user(alice)
    assert client.get(f"/coach/checks/{result['id']}").json()["id"] == result["id"]


def test_coach_requires_login(client: TestClient) -> None:
    assert client.post("/coach/check", json={"text": "Hallo"}).status_code == 401
    assert client.get("/coach/tasks").status_code == 401
