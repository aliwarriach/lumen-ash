from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.deps import get_cooldowns, get_limits, get_providers
from app.ai.errors import ProviderUnavailable
from app.ai.gateway import Cooldowns
from app.coach.deps import get_languagetool
from app.coach.languagetool import LtMatch
from app.main import app
from tests.conftest import SwitchUser
from tests.test_ai_gateway import FakeProvider
from tests.test_coach_api import FakeLanguageTool, add_dictionary

EXERCISE = (
    "Übung 3 Ergänzen Sie. 1 Ich ___ nach Hause. (gehen) 2 Er ___ ___ Tisch. (kaufen) "
    "3 Wie ___ du? 4 Sieh das Bild und ordne zu."
)
AI_ANSWER: dict[str, Any] = {
    "instruction": "Fill the gaps with the right verb form.",
    "items": [
        {
            "number": "1",
            "task": "Ich ___ nach Hause. (gehen)",
            "hint": "Which ending goes with 'ich'?",
            "answer": "gehe",
            "filled": "Ich gehe nach Hause.",
            "topic": "present_endings",
            "why": "With ich the verb ends in -e.",
            "unsure": False,
        },
        {
            "number": "2",
            "task": "Er ___ ___ Tisch. (kaufen)",
            "hint": "A masculine object needs a special article.",
            "answer": "kauft einen",
            "filled": "Er kauft einen Tisch.",
            "topic": "accusative",
            "why": "Tisch is masculine, so the object takes einen.",
            "unsure": False,
        },
        {
            "number": "3",
            "task": "Wie ___ du? (heißen)",
            "hint": "Which ending goes with 'du'?",
            "answer": "heißt",
            "filled": "Wie heißt du?",
            "topic": None,
            "why": None,
            "unsure": True,
        },
    ],
    "limits": "Item 4 needs the picture, so I left it out.",
}


def setup(languagetool: FakeLanguageTool | None, *providers: FakeProvider) -> None:
    app.dependency_overrides[get_languagetool] = lambda: languagetool
    app.dependency_overrides[get_providers] = lambda: providers
    app.dependency_overrides[get_limits] = lambda: replace(
        get_limits(), burst_per_minute=1000, user_requests=1000
    )


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    app.dependency_overrides[get_cooldowns] = Cooldowns
    yield
    for dep in (get_languagetool, get_providers, get_limits, get_cooldowns):
        app.dependency_overrides.pop(dep, None)


def add_verbs(db: Engine) -> None:
    add_dictionary(db)  # Tisch, Haus and gehen
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO dictionary_entries (source_key, lemma, lemma_lower, pos, genders,"
                " plurals, plural_only, meanings, verb_forms) VALUES ('kaufen|verb', 'kaufen',"
                " 'kaufen', 'verb', ARRAY[]::varchar[], ARRAY[]::varchar[], false, ARRAY['x'],"
                ' \'{"present": {"ich": "kaufe", "du": "kaufst", "er_sie_es": "kauft"}}\''
                "::jsonb)"
            )
        )


def help_me(client: TestClient, body: str = EXERCISE, status: int = 200) -> Any:
    response = client.post("/scanner/help", json={"text": body})
    assert response.status_code == status, response.text
    return response.json()


def test_each_answer_is_labelled_by_how_far_it_can_be_trusted(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_verbs(db)
    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))

    result = help_me(client)

    one, two, three = result["items"]
    # Our dictionary proves "ich gehe" and LanguageTool found nothing wrong.
    assert (one["task"], one["answer"], one["filled"]) == (
        "Ich ___ nach Hause. (gehen)",
        "gehe",
        "Ich gehe nach Hause.",
    )
    assert one["label"] == "confirmed" and one["warning"] is None
    assert "gehen" in one["verified_by"] and "'Ich'" in one["verified_by"]
    # The AI answered "kauft einen" and nothing proves it: Likely, never Confirmed.
    assert two["label"] == "likely" and two["verified_by"] is None
    assert two["pattern_key"] == "accusative" and two["pattern_title"]
    # The AI doubted this one itself.
    assert three["label"] == "uncertain" and three["warning"] == "Verify with your teacher."
    assert three["why"] is None and three["pattern_key"] is None
    assert result["instruction"] == "Fill the gaps with the right verb form."
    assert result["limits"] == "Item 4 needs the picture, so I left it out."
    assert result["checked_by"] == ["ai", "languagetool"] and result["cached"] is False


def test_languagetool_disagreeing_makes_an_answer_uncertain(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_verbs(db)
    # Offsets are in the joined text: the second sentence starts after "Ich gehe nach Hause.\n".
    start = len("Ich gehe nach Hause.\n")
    objection = LtMatch(start, start + 3, "DE_AGREEMENT", "GRAMMAR", "Check this.", ("Er",), None)
    setup(FakeLanguageTool(objection), FakeProvider("gemini", AI_ANSWER))

    one, two, _ = help_me(client)["items"]

    assert one["label"] == "confirmed"  # the objection is about item 2 only
    assert two["label"] == "uncertain" and two["warning"]


def test_without_languagetool_nothing_is_confirmed_and_the_learner_is_told(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_verbs(db)
    setup(FakeLanguageTool(down=True), FakeProvider("gemini", AI_ANSWER))

    result = help_me(client)

    assert [i["label"] for i in result["items"]] == ["likely", "likely", "uncertain"]
    assert result["checked_by"] == ["ai"]


def test_an_answer_that_does_not_fit_the_printed_exercise_is_uncertain(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    add_verbs(db)
    good = AI_ANSWER["items"][0]
    items = [
        # The answer isn't in the sentence the AI says it completes.
        {**good, "answer": "gehst"},
        # The AI rewrote the printed line instead of filling its gap.
        {**good, "filled": "Ich gehe heute in die Schule."},
        # A line with no gap ("write a question") has nothing to be compared with.
        {**good, "task": "du / wohnen / wo", "answer": "Wo wohnst du?", "filled": "Wo wohnst du?"},
        # The number copied into the line, and the clue in brackets, are not part of the sentence.
        {**good, "task": "1. Ich ___ nach Hause. (gehen)"},
    ]
    setup(FakeLanguageTool(), FakeProvider("gemini", {"items": items}))

    labels = [i["label"] for i in help_me(client)["items"]]

    assert labels == ["uncertain", "uncertain", "likely", "confirmed"]


def test_a_hint_that_gives_the_answer_away_is_replaced(
    client: TestClient, as_user: SwitchUser
) -> None:
    good = AI_ANSWER["items"][0]
    items = [
        {**good, "hint": "Use 'gehe', the form for ich."},
        {**good, "hint": "The form for ich is gehe.", "topic": None},
        {**good, "hint": "Which ending goes with 'ich'?"},
        # "in" is also an English word: it only counts as the answer when the hint quotes it.
        {**good, "task": "Ich wohne ___ Berlin.", "answer": "in", "filled": "Ich wohne in Berlin.",
         "hint": "Which preposition do you use for living in a city?"},
        {**good, "task": "Ich wohne ___ Berlin.", "answer": "in", "filled": "Ich wohne in Berlin.",
         "hint": "Use 'in' for cities.", "topic": None},
    ]  # fmt: skip
    setup(FakeLanguageTool(), FakeProvider("gemini", {"items": items}))

    hints = [i["hint"] for i in help_me(client)["items"]]

    assert hints[0].startswith("This is about: ") and "gehe" not in hints[0]
    assert (
        hints[1] == "Look at who or what the sentence is about, then at the word that is missing."
    )
    assert hints[2] == "Which ending goes with 'ich'?"
    assert hints[3] == "Which preposition do you use for living in a city?"
    assert hints[4] == hints[1]


def test_without_the_dictionary_a_correct_looking_answer_is_only_likely(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))
    assert help_me(client)["items"][0]["label"] == "likely"


def test_the_same_exercise_again_is_free(client: TestClient, as_user: SwitchUser) -> None:
    provider = FakeProvider("gemini", AI_ANSWER)
    setup(FakeLanguageTool(), provider)

    first = help_me(client)
    second = help_me(client)

    assert (first["cached"], second["cached"]) == (False, True)
    assert len(provider.requests) == 1
    quota = client.get("/ai/quota").json()
    used = next(f for f in quota["features"] if f["feature"] == "exercise_help")
    assert (used["used"], used["limit"], used["label"]) == (1, 15, "exercise helps")


def test_the_prompt_carries_only_the_exercise_with_personal_details_removed(
    client: TestClient, as_user: SwitchUser
) -> None:
    provider = FakeProvider("gemini", AI_ANSWER)
    setup(FakeLanguageTool(), provider)

    help_me(client, EXERCISE + " Frage an anna@example.com oder +92 300 1234567 oder www.klett.de")

    (request,) = provider.requests
    for secret in ("anna@example.com", "1234567", "klett.de"):
        assert secret not in request.user
    assert "Übung 3" in request.user


def test_nothing_is_stored(client: TestClient, as_user: SwitchUser, db: Engine) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))
    help_me(client)
    with db.connect() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'public' AND table_name LIKE '%scan%'"
                )
            )
        ]
        assert tables == []
        # Not even the learner's study data changed.
        assert conn.execute(text("SELECT count(*) FROM coach_checks")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM mistakes")).scalar_one() == 0


def test_an_exercise_the_text_cannot_answer_says_so(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(
        FakeLanguageTool(),
        FakeProvider("gemini", {"items": [], "limits": "The exercise is a listening task."}),
    )
    result = help_me(client)
    assert result["items"] == []
    assert result["limits"] == "The exercise is a listening task."


def test_an_empty_answer_gets_a_message_not_a_blank_screen(
    client: TestClient, as_user: SwitchUser
) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", {"items": []}))
    assert "could not work out any item" in help_me(client)["limits"]


def test_items_without_an_answer_are_dropped_and_extra_ones_cut(
    client: TestClient, as_user: SwitchUser
) -> None:
    good = AI_ANSWER["items"][0]
    items = [{**good, "answer": ""}, *[{**good, "task": f"Satz {n}"} for n in range(12)]]
    setup(FakeLanguageTool(), FakeProvider("gemini", {"items": items}))
    # Only the first 8 of the model's items are looked at; the empty one is one of them.
    assert len(help_me(client)["items"]) == 7


def test_an_unknown_topic_is_ignored_not_an_error(client: TestClient, as_user: SwitchUser) -> None:
    item = {**AI_ANSWER["items"][0], "topic": "made_up_topic"}
    setup(FakeLanguageTool(), FakeProvider("gemini", {"items": [item]}))
    (out,) = help_me(client)["items"]
    assert out["pattern_key"] is None and out["why"] == item["why"]


def test_the_ai_being_down_is_a_clear_error(client: TestClient, as_user: SwitchUser) -> None:
    setup(FakeLanguageTool(), FakeProvider("gemini", ProviderUnavailable("down")))
    detail = help_me(client, status=503)["detail"]
    assert "AI help isn't available" in detail["message"]


def test_a_bad_photo_with_hardly_any_text_is_refused_before_the_ai_is_asked(
    client: TestClient, as_user: SwitchUser
) -> None:
    provider = FakeProvider("gemini", AI_ANSWER)
    setup(FakeLanguageTool(), provider)
    assert "not enough text" in str(help_me(client, "Ü 3", status=422)["detail"])
    help_me(client, "", status=422)
    help_me(client, "wort " * 600, status=422)
    assert provider.requests == []


def test_a_full_page_of_text_is_accepted_and_more_than_that_is_refused(
    client: TestClient, as_user: SwitchUser
) -> None:
    provider = FakeProvider("gemini", AI_ANSWER)
    setup(FakeLanguageTool(), provider)
    help_me(client, "wort " * 480)  # 2400 characters: the most the AI template has room for
    assert len(provider.requests) == 1
    help_me(client, "wort " * 481, status=422)


def test_the_scanner_requires_login(client: TestClient) -> None:
    assert client.post("/scanner/help", json={"text": EXERCISE}).status_code in (401, 403)
