"""Grammar practice: the fixed exercises, and answers counting towards a pattern's accuracy."""

import uuid
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.grammar.catalog import PatternKey
from app.grammar.exercises import BOOK_CHAPTER, BY_ID, EXERCISES, ExerciseKind, is_correct
from app.review.grading import normalize
from tests.conftest import SwitchUser

ALL = [ex for exercises in EXERCISES.values() for ex in exercises]


# --- The content itself -------------------------------------------------------------------------


def test_every_pattern_has_a_chapter_and_enough_exercises() -> None:
    assert set(EXERCISES) == set(PatternKey) == set(BOOK_CHAPTER)
    for key, exercises in EXERCISES.items():
        assert len(exercises) >= 8, key
    assert len(BY_ID) == len(ALL), "exercise ids must be unique"


@pytest.mark.parametrize("ex", ALL, ids=lambda ex: ex.id)
def test_each_exercise_is_answerable_by_its_own_rules(ex: object) -> None:
    from app.grammar.exercises import Exercise

    assert isinstance(ex, Exercise)
    assert ex.answers and ex.hint and ex.why
    # Every accepted answer passes the checker, and the empty answer does not.
    for answer in ex.answers:
        assert is_correct(ex, answer), answer
    assert not is_correct(ex, "")

    if ex.kind is ExerciseKind.CHOICE:
        assert len(ex.options) >= 2 and len(set(ex.options)) == len(ex.options)
        assert ex.answers[0] in ex.options
        assert len(ex.answers) == 1
        wrong = [o for o in ex.options if o != ex.answers[0]]
        assert not any(is_correct(ex, o) for o in wrong), "a wrong option must not pass"
    if ex.kind in (ExerciseKind.CHOICE, ExerciseKind.FILL) and "___" not in ex.prompt:
        assert ex.prompt == "Which sentence is right?" or "…" in ex.prompt
    if ex.kind is ExerciseKind.FILL:
        assert "___" in ex.prompt and ex.english
    if ex.kind is ExerciseKind.ORDER:
        assert len(ex.tiles) >= 3 and ex.end in {".", "?"}
        tiles = Counter(t.casefold() for t in ex.tiles)
        for answer in ex.answers:
            # Every accepted order can be built from exactly the tiles shown.
            assert Counter(w.casefold() for w in normalize(answer).split(" ")) == tiles, answer
            assert not answer.endswith((".", "?"))
        # The tiles shuffled into a wrong order are not accepted.
        assert not is_correct(ex, " ".join(reversed(ex.tiles)))


def test_answers_are_checked_like_review_answers() -> None:
    fill = BY_ID["pe-1"][1]  # Ich ___ aus Pakistan. (kommen) → komme
    assert is_correct(fill, "komme") and is_correct(fill, "  Komme. ")
    assert not is_correct(fill, "kommen")

    capital = BY_ID["cs-4"][1]  # a noun: the capital letter is the point
    assert is_correct(capital, "Milch") and not is_correct(capital, "milch")

    choice = BY_ID["cs-1"][1]  # sentences that differ only in capitals
    assert not is_correct(choice, "Ich habe einen hund.")

    order = BY_ID["v2-1"][1]
    assert is_correct(order, "Heute lerne ich Deutsch")
    assert is_correct(order, "ich lerne Heute Deutsch")  # the other right order, from the tiles
    assert not is_correct(order, "Heute ich lerne Deutsch")


# --- The API ------------------------------------------------------------------------------------


def test_a_practice_set_has_the_exercises_in_order(client: TestClient, as_user: SwitchUser) -> None:
    body = client.get("/grammar/patterns/accusative/practice").json()

    assert body["key"] == "accusative" and body["book_chapter"] == 4
    assert [e["id"] for e in body["exercises"]] == [e.id for e in EXERCISES[PatternKey.ACCUSATIVE]]
    first = body["exercises"][0]
    assert first["kind"] == "choice" and first["options"] == ["der", "den", "dem"]
    assert first["answers"] == ["den"] and first["hint"] and first["why"]

    order = client.get("/grammar/patterns/verb_second/practice").json()["exercises"][0]
    assert order["kind"] == "order" and order["tiles"] == ["Heute", "lerne", "ich", "Deutsch"]


def test_the_pattern_list_follows_the_book(client: TestClient, as_user: SwitchUser) -> None:
    patterns = client.get("/grammar/patterns").json()

    chapters = [p["book_chapter"] for p in patterns]
    assert chapters == sorted(chapters)
    assert all(p["exercise_count"] >= 8 for p in patterns)


def test_practice_answers_fill_the_tracker(client: TestClient, as_user: SwitchUser) -> None:
    def answer(exercise_id: str, given: str) -> dict[str, object]:
        response = client.post(
            "/grammar/practice/answers", json={"exercise_id": exercise_id, "given": given}
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert answer("ak-1", "den") == {
        "correct": True,
        "expected": "den",
        "pattern_key": "accusative",
    }
    assert answer("ak-2", "ein")["correct"] is False
    answer("ak-3", "einen")

    p = client.get("/grammar/patterns/accusative").json()
    assert (p["stats"]["attempts"], p["stats"]["correct"]) == (3, 2)
    assert p["stats"]["level"] == "weak"  # 2 of 3 is under 70%
    latest = p["evidence"][0]
    assert latest["source"] == "practice" and latest["label"] == "Practice"
    assert (latest["given"], latest["expected"]) == ("einen", "einen")

    weak = client.get("/grammar/weak").json()
    assert weak[0]["key"] == "accusative"
    assert weak[0]["evidence"][0]["given"] == "ein"  # the wrong answer is shown


def test_the_server_decides_and_unknown_exercises_are_refused(
    client: TestClient, as_user: SwitchUser
) -> None:
    post = client.post
    assert (
        post("/grammar/practice/answers", json={"exercise_id": "nope", "given": "x"}).status_code
        == 404
    )
    assert (
        post(
            "/grammar/practice/answers", json={"exercise_id": "ak-1", "given": "x" * 301}
        ).status_code
        == 422
    )
    assert (
        post("/grammar/practice/answers", json={"exercise_id": "ak-1", "given": "dem"}).json()[
            "correct"
        ]
        is False
    )


def test_practice_answers_belong_to_the_learner_who_gave_them(
    client: TestClient, as_user: SwitchUser
) -> None:
    client.post("/grammar/practice/answers", json={"exercise_id": "ne-1", "given": "nicht"})

    as_user(uuid.uuid4())
    p = client.get("/grammar/patterns/negation").json()
    assert p["stats"]["attempts"] == 0 and p["evidence"] == []
