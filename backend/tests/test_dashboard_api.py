import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import SwitchUser
from tests.test_ai_gateway import FakeProvider
from tests.test_coach_api import AI_ANSWER, FakeLanguageTool, check, reset_overrides, setup
from tests.test_course import add_resource, create_chapter, set_completed
from tests.test_mistakes import ACCUSATIVE, log
from tests.test_review_api import GEHEN, TISCH, Clock, add_word, answer, card_of, clock, queue

__all__ = ["clock", "reset_overrides"]  # fixtures, re-used from other test modules


def dashboard(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/dashboard", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def study(client: TestClient) -> None:
    """Answers whichever card comes first in today's queue."""
    card = queue(client)["cards"][0]
    answer(client, card, rating=3, text="der Tisch", article="der", plural="Tische")


def item(board: dict[str, Any], kind: str) -> dict[str, Any] | None:
    return next((i for i in board["plan"]["items"] if i["kind"] == kind), None)


# --- A learner with nothing yet ---


def test_a_new_learner_still_gets_an_answer_to_each_of_the_four_questions(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    board = dashboard(client)

    # 1. Am I on track?
    assert board["on_track"]["status"] == "getting_started"
    assert board["on_track"]["streak"] == 0 and board["on_track"]["reason"]
    # 2. What should I do today?
    assert [i["kind"] for i in board["plan"]["items"]] == ["writing", "listening", "speaking"]
    assert all(i["why"] and i["minutes"] > 0 for i in board["plan"]["items"])
    assert board["plan"]["total_minutes"] <= 60
    # 3. Where am I weak?
    assert board["grammar"] == {"attempts": 0, "correct": 0, "accuracy": None, "weak": []}
    assert board["weak_words"] == [] and board["mistakes"]["recent"] == []
    # 4. Am I ready for the next test? No test yet, so it says how to get an answer.
    assert board["test"]["next"] is None
    assert board["test"]["message"].startswith("No test coming up.")

    assert board["cards"] == {"due": 0, "new": 0, "reviewed_today": 0}
    assert board["vocabulary"]["total"] == 0 and board["chapters"]["current"] is None
    assert board["date"] == "2026-11-10"


def test_the_dashboard_requires_login_and_a_real_timezone(client: TestClient) -> None:
    assert client.get("/dashboard").status_code == 401


def test_an_unknown_timezone_is_rejected(client: TestClient, as_user: SwitchUser) -> None:
    assert client.get("/dashboard", params={"tz": "Mars/Base"}).status_code == 422


def test_the_date_is_the_learners_local_date(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    clock.advance(hours=15)  # 24:00 UTC: already the 11th in Karachi (UTC+5)
    assert dashboard(client)["date"] == "2026-11-11"
    assert dashboard(client, tz="Asia/Karachi")["date"] == "2026-11-11"
    clock.advance(hours=-1)
    assert dashboard(client)["date"] == "2026-11-10"
    assert dashboard(client, tz="Asia/Karachi")["date"] == "2026-11-11"


# --- Cards due ---


def test_cards_due_always_matches_the_review_queue(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client, TISCH)
    add_word(client, GEHEN)
    log(client)  # a mistake retry card, due straight away

    before = dashboard(client)
    q = queue(client)
    assert (before["cards"]["due"], before["cards"]["new"]) == (q["due_count"], q["new_count"])
    assert before["cards"]["due"] >= 1  # the retry card

    answer(client, card_of(client, "recall"))
    after, q = dashboard(client), queue(client)
    assert (after["cards"]["due"], after["cards"]["new"]) == (q["due_count"], q["new_count"])
    assert after["cards"]["reviewed_today"] == 1

    review = item(after, "review")
    assert review is not None and review["done"] is False
    assert f"{after['cards']['due']} card" in review["why"] and "mistake retr" in review["why"]


def test_the_review_item_is_ticked_once_everything_due_is_done(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client, GEHEN)  # a verb has a recall and a produce card
    before = dashboard(client)
    assert (before["cards"]["due"], before["cards"]["new"]) == (0, 2)
    assert item(before, "review")["done"] is False  # type: ignore[index]

    # "Easy" sends each card days away, but also moves the word up a stage, which unlocks its
    # sentence card: one new card is still waiting.
    answer(client, card_of(client, "recall"), rating=4)
    answer(client, card_of(client, "produce"), rating=4, text="gehen")
    middle = dashboard(client)
    assert (middle["cards"]["due"], middle["cards"]["new"]) == (0, 1)
    review = item(middle, "review")
    assert review is not None and review["done"] is False
    assert (review["title"], review["why"]) == ("Review 1 card", "1 new card to start.")

    answer(client, card_of(client, "sentence"), rating=4, text="Ich gehe nach Hause.")
    after = dashboard(client)
    assert (after["cards"]["due"], after["cards"]["new"]) == (0, 0)
    assert after["cards"]["reviewed_today"] == 3
    review = item(after, "review")
    assert review is not None and review["done"] is True
    assert review["why"] == "All done: you reviewed 3 cards today."
    assert after["plan"]["remaining_minutes"] == after["plan"]["total_minutes"] - review["minutes"]


# --- Streak and on track ---


def test_studying_on_consecutive_days_builds_a_streak_and_missing_days_breaks_it(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client, TISCH)
    for _ in range(3):  # three days in a row
        study(client)
        clock.advance(days=1)
    # It is now the 4th day and the learner hasn't studied yet: the streak is still alive.
    board = dashboard(client)
    assert board["on_track"]["streak"] == 3 and board["on_track"]["days_studied"] == 3
    assert board["on_track"]["status"] == "on_track"
    assert board["on_track"]["last_studied"] == "2026-11-12"
    # Tuesday to Thursday of the week that began on Monday the 9th.
    assert board["on_track"]["week"] == ["2026-11-10", "2026-11-11", "2026-11-12"]

    study(client)
    assert dashboard(client)["on_track"]["streak"] == 4

    clock.advance(days=3)  # nothing for two full days
    board = dashboard(client)
    assert board["on_track"]["streak"] == 0
    assert board["on_track"]["week"] == []  # Monday the 16th: a new week
    assert board["on_track"]["status"] == "slipping"
    assert "You last studied 3 days ago" in board["on_track"]["reason"]


def test_study_days_use_the_learners_timezone(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    add_word(client, TISCH)
    clock.advance(hours=15)  # 24:00 UTC on the 10th = 05:00 on the 11th in Karachi
    answer(client, card_of(client, "recall"))
    clock.advance(hours=-1)  # 23:00 UTC = 04:00 Karachi: still the 11th there, the 10th in UTC
    answer(client, card_of(client, "article"))
    clock.advance(hours=1, days=1)  # 24:00 UTC on the 11th

    karachi = dashboard(client, tz="Asia/Karachi")["on_track"]
    utc = dashboard(client, tz="UTC")["on_track"]
    assert karachi["last_studied"] == "2026-11-11" and utc["last_studied"] == "2026-11-11"
    assert karachi["days_studied"] == 1  # both answers were the Karachi 11th
    assert utc["days_studied"] == 2  # but the UTC 10th and 11th


def test_writing_and_finishing_chapter_resources_count_as_studying(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    chapter = create_chapter(client, 1)
    resource = add_resource(client, chapter["id"], kind="workbook_exercise")
    set_completed(client, resource["id"], True)  # stamped with the real current time
    assert dashboard(client)["on_track"]["status"] != "getting_started"


# --- Weak areas ---


def test_weak_patterns_and_words_come_from_the_learners_own_mistakes(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    tisch = add_word(client, TISCH)
    log(client, word_ids=[tisch["id"]])
    clock.advance(minutes=5)
    log(client, wrong="Ich sehe der Mann.", correct="Ich sehe den Mann.")
    answer(client, card_of(client, "produce", tisch["id"]), rating=3, text="Tisch")  # no article

    board = dashboard(client)
    (weak,) = board["grammar"]["weak"]
    assert weak["key"] == "accusative" and weak["title"] == "Accusative case: den, einen"
    assert "2 wrong out of 2 in the last 30 days" in weak["reason"]
    assert board["grammar"]["attempts"] >= 2 and board["grammar"]["accuracy"] is not None

    (word,) = board["weak_words"]
    assert (word["german"], word["article"], word["wrong"], word["attempts"]) == (
        "Tisch",
        "der",
        1,
        1,
    )
    assert word["reason"] == "1 wrong out of 1 checked answers in the last 30 days."

    assert board["mistakes"]["last_7_days"] == 2
    assert [m["wrong"] for m in board["mistakes"]["recent"]][0] == "Ich sehe der Mann."

    # The plan turns the weakest pattern into today's grammar item, with the same reason.
    grammar = item(board, "grammar")
    assert grammar is not None
    assert (grammar["pattern_key"], grammar["why"]) == ("accusative", weak["reason"])
    speaking = item(board, "speaking")
    assert speaking is not None and speaking["words"] == ["der Tisch"]
    assert "got wrong most recently" in speaking["why"]


def test_with_nothing_wrong_the_grammar_item_picks_a_thin_pattern_from_the_current_chapter(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    chapter = create_chapter(client, 1)
    assert (
        client.put(
            "/grammar/patterns/verb_second/chapters", json={"chapter_ids": [chapter["id"]]}
        ).status_code
        == 200
    )
    grammar = item(dashboard(client), "grammar")
    assert grammar is not None and grammar["pattern_key"] == "verb_second"
    assert "haven't answered anything about it in 30 days" in grammar["why"]


def test_the_grammar_item_is_ticked_once_the_pattern_is_practised_today(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    m = log(client)
    assert item(dashboard(client), "grammar")["done"] is True  # type: ignore[index]
    # (the logged mistake itself is evidence for today)
    assert m["pattern_key"] == ACCUSATIVE["pattern_key"]


# --- Chapters, homework and listening ---


def test_homework_and_audio_come_from_the_current_chapter_and_tick_when_marked_done(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    one = create_chapter(client, 1)
    work = add_resource(
        client, one["id"], kind="workbook_exercise", title="Übung 3", reference="S. 24"
    )
    audio = add_resource(client, one["id"], kind="audio", title="Dialog 1")
    add_resource(client, one["id"], kind="video", title="Erklärvideo")
    two = create_chapter(client, 2)
    later_work = add_resource(client, two["id"], kind="workbook_exercise", title="Übung 9")

    board = dashboard(client)
    assert board["chapters"]["total"] == 2 and board["chapters"]["completed"] == 0
    assert board["chapters"]["current"]["number"] == 1
    homework = item(board, "homework")
    assert homework is not None and homework["resource_id"] == work["id"]
    assert homework["title"] == "Workbook: Übung 3 (S. 24)" and homework["done"] is False
    listening = item(board, "listening")
    assert listening is not None and listening["resource_id"] == audio["id"]
    assert listening["done"] is False
    # Chapter 2 hasn't started: its homework isn't pending yet.
    assert later_work["id"] not in [i["resource_id"] for i in board["plan"]["items"]]

    set_completed(client, work["id"], True)
    set_completed(client, audio["id"], True)
    board = dashboard(client)
    assert item(board, "homework")["done"] is True  # type: ignore[index]
    assert item(board, "listening")["done"] is True  # type: ignore[index]
    assert board["chapters"]["resources_done"] == 2 and board["chapters"]["resources_total"] == 4


def test_the_current_chapter_moves_on_when_one_is_finished_and_older_homework_stays(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    one = create_chapter(client, 1)
    left_behind = add_resource(client, one["id"], kind="workbook_exercise", title="Übung 1")
    finished = add_resource(client, one["id"], kind="audio", title="Dialog 1")
    two = create_chapter(client, 2)
    now_work = add_resource(client, two["id"], kind="workbook_exercise", title="Übung 5")

    set_completed(client, finished["id"], True)
    assert dashboard(client)["chapters"]["current"]["number"] == 1  # chapter 1 isn't finished

    set_completed(client, left_behind["id"], True)
    board = dashboard(client)
    assert board["chapters"]["completed"] == 1
    assert board["chapters"]["current"]["number"] == 2  # moved on
    pending = [i for i in board["plan"]["items"] if i["kind"] == "homework" and not i["done"]]
    assert [i["resource_id"] for i in pending] == [now_work["id"]]


# --- Writing ---


def test_the_writing_item_follows_the_open_task_and_is_ticked_when_enough_is_written(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    task = client.post(
        "/coach/tasks", json={"prompt": "5 sentences about your day", "min_sentences": 5}
    ).json()
    writing = item(dashboard(client), "writing")
    assert writing is not None and writing["task_id"] == task["id"] and writing["done"] is False

    setup(FakeLanguageTool(), FakeProvider("gemini", AI_ANSWER))
    check(
        client, "Ich stehe auf. Ich esse. Ich lerne. Ich arbeite. Ich schlafe.", task_id=task["id"]
    )

    board = dashboard(client)
    writing = item(board, "writing")
    assert writing is not None and writing["done"] is True
    assert "You've checked 5 sentences today." in writing["why"]
    assert board["on_track"]["status"] != "getting_started"  # writing counts as studying


# --- The plan as a whole ---


def test_a_busy_learners_plan_fits_the_hour_and_every_item_explains_itself(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    for i in range(8):
        add_word(client, {**TISCH, "german": f"Wort{i}", "plural": f"Wörter{i}"})
    log(client)
    chapter = create_chapter(client, 1)
    for n in range(3):
        add_resource(client, chapter["id"], kind="workbook_exercise", title=f"Übung {n}")
    add_resource(client, chapter["id"], kind="audio", title="Dialog")
    client.post("/coach/tasks", json={"prompt": "Write about your day"})

    plan = dashboard(client)["plan"]
    assert plan["total_minutes"] <= 60
    assert 0 < plan["remaining_minutes"] <= plan["total_minutes"]
    assert all(i["why"].strip() and i["minutes"] > 0 for i in plan["items"])
    ids = [i["id"] for i in plan["items"]]
    assert len(set(ids)) == len(ids)
    assert plan["items"][0]["kind"] == "review"  # due reviews come first


# --- Privacy ---


def test_one_learners_dashboard_shows_nothing_of_anothers(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    alice, bob = uuid.uuid4(), uuid.uuid4()
    as_user(alice)
    add_word(client, TISCH)
    log(client)
    create_chapter(client, 1)
    answer(client, card_of(client, "recall"))
    assert dashboard(client)["vocabulary"]["total"] == 1

    as_user(bob)
    board = dashboard(client)
    assert board["on_track"]["status"] == "getting_started"
    assert board["vocabulary"]["total"] == 0 and board["chapters"]["total"] == 0
    assert board["mistakes"]["recent"] == [] and board["grammar"]["weak"] == []
    assert board["cards"] == {"due": 0, "new": 0, "reviewed_today": 0}
