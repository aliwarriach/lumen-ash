"""Sentence lessons: the fixed content, the learner's own words, and saved scores."""

import uuid
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from app.dictionary.models import DictionaryEntry
from app.review.grading import normalize
from app.sentences.content import (
    LESSONS,
    BlankRule,
    SentenceExercise,
    SentenceKind,
    blank_problem,
    is_correct,
    same_tiles,
)
from app.sentences.router import example_exercise
from tests.conftest import SwitchUser

ALL = [ex for lesson in LESSONS for ex in lesson.exercises]


def test_one_lesson_per_chapter_with_every_kind() -> None:
    assert [lesson.book_chapter for lesson in LESSONS] == [1, 2, 3, 4, 5, 6]
    assert len({ex.id for ex in ALL}) == len(ALL), "exercise ids must be unique"
    assert len({lesson.id for lesson in LESSONS}) == len(LESSONS)
    for lesson in LESSONS:
        assert len(lesson.exercises) >= 8, lesson.id
        assert {ex.kind for ex in lesson.exercises} == set(SentenceKind), lesson.id
        assert lesson.exercises[-1].kind is SentenceKind.FRAME, "guided writing comes last"


@pytest.mark.parametrize("ex", ALL, ids=lambda ex: ex.id)
def test_each_exercise_is_answerable_by_its_own_rules(ex: SentenceExercise) -> None:
    assert ex.answers and ex.hint and ex.why and ex.prompt
    if ex.kind is SentenceKind.FRAME:
        assert ex.prompt.count("___") == len(ex.blanks) >= 1
        for blank in ex.blanks:
            assert blank_problem(blank, blank.example) is None, blank
            assert blank_problem(blank, "") is not None
            assert blank.example in ex.answers[0], "the model answer uses the examples"
        return

    for answer in ex.answers:
        assert is_correct(ex, answer), answer
    assert not is_correct(ex, "")

    if ex.kind is SentenceKind.CHOICE:
        assert ex.answers[0] in ex.options and len(set(ex.options)) == len(ex.options) >= 2
        assert not any(is_correct(ex, o) for o in ex.options if o != ex.answers[0])
    if ex.kind is SentenceKind.FILL:
        assert "___" in ex.prompt and ex.english
    if ex.kind in (SentenceKind.ORDER, SentenceKind.BANK):
        assert ex.end in {".", "?"} and len(ex.tiles) >= 3
        words = Counter(t.casefold() for t in ex.answers[0].split(" "))
        for answer in ex.answers:
            assert not answer.endswith((".", "?"))
            # Each accepted order uses exactly the sentence's words, never an extra tile.
            assert Counter(w.casefold() for w in normalize(answer).split(" ")) == words, answer
            assert same_tiles(answer, ex.tiles)
        assert not is_correct(ex, " ".join(reversed(ex.answers[0].split(" "))))
    if ex.kind is SentenceKind.BANK:
        assert len(ex.distractors) >= 2
        assert not set(d.casefold() for d in ex.distractors) & {
            w.casefold() for w in ex.answers[0].split(" ")
        }, "an extra tile must not also be a real word of the sentence"
        assert not is_correct(ex, f"{ex.answers[0]} {ex.distractors[0]}")


def test_frame_gaps_are_checked_by_simple_rules() -> None:
    k1 = next(ex for ex in ALL if ex.id == "k1-10")
    name = k1.blanks[0]
    assert name.rule is BlankRule.CAPITAL
    assert blank_problem(name, "Sara") is None
    assert "capital" in (blank_problem(name, "sara") or "")

    verb = next(ex for ex in ALL if ex.id == "k2-10").blanks[1]
    assert blank_problem(verb, "lese") is None
    assert "-e" in (blank_problem(verb, "lesen") or "")
    assert "small letter" in (blank_problem(verb, "Lese") or "")

    month = next(ex for ex in ALL if ex.id == "k6-10").blanks[1]
    assert blank_problem(month, "März") is None and blank_problem(month, "mai") is not None
    assert "isn't one of" in (blank_problem(month, "Montag") or "")


def test_dictionary_examples_become_tile_exercises_only_when_plain_and_short() -> None:
    wid = uuid.uuid4()
    ex = example_exercise(wid, "Tisch", "Kommt, der Tisch ist gedeckt!", "Come, the table is set!")
    assert ex is not None and ex.kind is SentenceKind.ORDER
    assert ex.answers == ("Kommt, der Tisch ist gedeckt",) and ex.end == "!"
    assert ex.tiles == ("Kommt,", "der", "Tisch", "ist", "gedeckt")

    assert example_exercise(wid, "x", "Zu kurz.", "Too short.") is None
    assert example_exercise(wid, "x", "Er sagte: »Ja«.", "He said yes.") is None
    long = "Das ist ein sehr langer Satz mit viel zu vielen Wörtern darin."
    assert example_exercise(wid, "x", long, "A long sentence.") is None


# --- The API ------------------------------------------------------------------------------------


def test_lessons_are_listed_in_course_order_with_no_scores_yet(
    client: TestClient, as_user: SwitchUser
) -> None:
    lessons = client.get("/sentences/lessons").json()

    assert [x["book_chapter"] for x in lessons] == [1, 2, 3, 4, 5, 6, None]
    assert lessons[0]["title"] == "Guten Tag!" and lessons[0]["best_right"] is None
    assert lessons[-1]["id"] == "my-words" and lessons[-1]["exercise_count"] == 0

    lesson = client.get("/sentences/lessons/k1-hallo").json()
    assert lesson["exercises"][0]["kind"] == "order"
    frame = lesson["exercises"][-1]
    assert frame["kind"] == "frame" and len(frame["blanks"]) == 3
    assert frame["blanks"][0]["rule"] == "capital"
    bank = next(e for e in lesson["exercises"] if e["kind"] == "bank")
    assert set(bank["distractors"]) <= set(bank["tiles"])

    assert client.get("/sentences/lessons/nope").status_code == 404


def test_my_words_uses_the_dictionary_examples_of_saved_words(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    with db.begin() as conn:
        conn.execute(
            insert(DictionaryEntry),
            [
                {
                    "source_key": "Tisch|noun|0|1",
                    "lemma": "Tisch",
                    "lemma_lower": "tisch",
                    "pos": "noun",
                    "genders": ["m"],
                    "plurals": ["Tische"],
                    "plural_only": False,
                    "meanings": ["table"],
                    "example_de": "Der Tisch ist gedeckt.",
                    "example_en": "The table is set.",
                }
            ],
        )
    word = {"kind": "noun", "german": "Tisch", "article": "der", "meaning_en": "table"}
    assert (
        client.post("/words", json={**word, "dictionary_key": "Tisch|noun|0|1"}).status_code == 201
    )
    assert (
        client.post("/words", json={**word, "german": "Stuhl", "meaning_en": "chair"}).status_code
        == 201
    )

    summary = client.get("/sentences/lessons").json()[-1]
    assert summary["exercise_count"] == 1  # only the word with a dictionary example
    exercise = client.get("/sentences/lessons/my-words").json()["exercises"][0]
    assert exercise["prompt"] == "The table is set."
    assert exercise["tiles"] == ["Der", "Tisch", "ist", "gedeckt"]

    as_user(uuid.uuid4())  # someone else sees none of it
    assert client.get("/sentences/lessons").json()[-1]["exercise_count"] == 0


def test_a_result_keeps_the_best_round_and_the_latest(
    client: TestClient, as_user: SwitchUser
) -> None:
    def save(right: int, total: int = 10) -> dict[str, object]:
        response = client.post(
            "/sentences/lessons/k1-hallo/result", json={"right": right, "total": total}
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert save(6)["best_right"] == 6
    after = save(4)
    assert (after["best_right"], after["last_right"], after["rounds"]) == (6, 4, 2)
    assert save(9)["best_right"] == 9

    listed = client.get("/sentences/lessons").json()[0]
    assert (listed["best_right"], listed["rounds"]) == (9, 3)

    assert (
        client.post("/sentences/lessons/nope/result", json={"right": 1, "total": 2}).status_code
        == 404
    )
    assert (
        client.post("/sentences/lessons/k1-hallo/result", json={"right": 5, "total": 2}).status_code
        == 422
    )

    as_user(uuid.uuid4())
    assert client.get("/sentences/lessons").json()[0]["best_right"] is None
