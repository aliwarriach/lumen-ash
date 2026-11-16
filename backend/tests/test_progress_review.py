"""The progress review: honest numbers, praise only for real gains, encouragement when it's hard."""

from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient

from app.progress.review import Numbers, Tone, achievements, change_text, headline_and_message, tone
from tests.conftest import SwitchUser

BASE = Numbers(
    studied_ever=True,
    days_this_week=4,
    days_last_week=2,
    streak=4,
    cards_this_week=30,
    cards_last_week=20,
    answers_this_week=40,
    right_this_week=36,
    words_total=12,
    words_added_this_week=5,
    words_mastered=1,
    lessons_completed=1,
    rules_strong=1,
    resources_done_this_week=2,
)
PRAISE = ("Fantastic", "Good work", "great", "streak", "right this week", "more than last week")


def test_a_new_learner_is_welcomed_with_a_first_step() -> None:
    n = replace(BASE, studied_ever=False, days_this_week=0, streak=0, answers_this_week=0)
    t, headline, message = headline_and_message(n)
    assert t is Tone.START and "started" in headline and "Kapitel 1" in message


def test_a_strong_week_is_praised_with_its_real_numbers() -> None:
    t, headline, message = headline_and_message(BASE)
    assert t is Tone.GREAT and headline == "Fantastic week!" and "4 days" in message
    wins = achievements(BASE)
    assert wins[0] == "🔥 4-day streak!"
    assert "You studied on 2 more days than last week." in wins
    assert "90% of your answers were right this week." in wins
    assert "You reviewed 30 cards this week, 10 more than last week." in wins
    assert "You have collected 10+ words!" in wins


def test_a_hard_week_gets_honest_encouragement_and_no_praise_for_the_results() -> None:
    n = replace(BASE, right_this_week=20)  # 50%
    t, headline, message = headline_and_message(n)
    assert t is Tone.KEEP_GOING
    assert "50%" in message and "Don't give up" in message and "normal" in message
    assert not any(word in headline for word in ("Fantastic", "Good work"))
    assert not any("right this week" in w for w in achievements(n)), "a low score is not praised"


def test_coming_back_after_a_break_is_never_blamed() -> None:
    n = replace(
        BASE, days_this_week=0, streak=0, cards_this_week=0, answers_this_week=0, right_this_week=0
    )
    t, headline, message = headline_and_message(n)
    assert t is Tone.WELCOME_BACK and "nothing is lost" in message
    assert "lazy" not in message.lower() and "should have" not in message.lower()


def test_a_drop_is_a_plain_fact_never_an_achievement() -> None:
    n = replace(BASE, days_this_week=2, days_last_week=5, cards_this_week=10, cards_last_week=40)
    wins = achievements(n)
    assert not any("more" in w for w in wins)
    assert change_text(10, 40) == ("30 fewer than last week", None)
    assert change_text(5, 2) == ("+3 on last week", True)
    assert change_text(3, 3) == ("same as last week", None)


def test_a_good_but_thin_week_gets_one_concrete_tip() -> None:
    n = replace(BASE, days_this_week=2, right_this_week=32)  # 80%, only two days
    t, headline, message = headline_and_message(n)
    assert t is Tone.GOOD and "3 or 4 days" in message


def test_too_few_answers_are_not_judged() -> None:
    n = replace(BASE, answers_this_week=3, right_this_week=0)
    assert tone(n) is Tone.GREAT  # 4 days of study; 3 answers say nothing about accuracy
    assert not any("right this week" in w for w in achievements(n))


# --- The API ------------------------------------------------------------------------------------


def review(client: TestClient) -> Any:
    response = client.get("/progress/review", params={"tz": "Asia/Karachi"})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_fresh_account_gets_a_welcome_and_its_first_steps(
    client: TestClient, as_user: SwitchUser
) -> None:
    body = review(client)

    assert body["tone"] == "start" and body["achievements"] == []
    titles = [s["title"] for s in body["to_do"]]
    assert "Next sentence lesson" in titles and "Next grammar rule" in titles
    lesson = next(s for s in body["to_do"] if s["title"] == "Next sentence lesson")
    assert lesson["link"] == "/sentences/k1-hallo"
    assert body["improve"] is None
    assert [m["label"] for m in body["this_week"]][0] == "Days studied"


def test_practice_counts_as_study_and_a_bad_round_is_handled_kindly(
    client: TestClient, as_user: SwitchUser
) -> None:
    for exercise_id in ("ak-1", "ak-2", "ak-3", "ak-4", "ak-5", "ak-6", "ak-7", "ak-8"):
        client.post("/grammar/practice/answers", json={"exercise_id": exercise_id, "given": "x"})

    body = review(client)
    assert body["tone"] == "keep_going"
    assert "0%" in str(body["message"]) and "Don't give up" in str(body["message"])
    days = next(m for m in body["this_week"] if m["label"] == "Days studied")
    assert days["value"] == 1
    grammar = next(m for m in body["this_week"] if m["label"] == "Grammar answers")
    assert grammar["value"] == 8
    improve = body["improve"]
    assert isinstance(improve, dict) and improve["link"] == "/mistakes"
    assert "1 grammar rule needs more practice" in improve["detail"]


def test_a_lesson_round_shows_as_progress_and_the_next_lesson_moves_on(
    client: TestClient, as_user: SwitchUser
) -> None:
    client.post("/sentences/lessons/k1-hallo/result", json={"right": 9, "total": 10})
    client.post("/sentences/lessons/k2-leute/result", json={"right": 4, "total": 10})

    body = review(client)
    assert "1 sentence lesson completed." in body["achievements"]
    under_way = next(s for s in body["in_progress"] if s["title"] == "Sentences: Leute")
    assert under_way["detail"].startswith("Best so far: 4 of 10")
    lesson = next(s for s in body["to_do"] if s["title"] == "Next sentence lesson")
    assert lesson["link"] == "/sentences/k3-stadt"
