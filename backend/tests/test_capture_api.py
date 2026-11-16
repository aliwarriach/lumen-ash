import uuid
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.deps import get_cooldowns, get_limits, get_providers
from app.ai.errors import ProviderUnavailable
from app.ai.gateway import Cooldowns
from app.ai.prompts import CAPTURE_KINDS, MessageCaptureOut
from app.capture.models import TaskKind
from app.main import app
from tests.conftest import SwitchUser
from tests.test_ai_gateway import FakeProvider
from tests.test_review_api import Clock, clock

__all__ = ["clock"]  # the fixture, re-used from the review tests

# "Today" in these tests is Tuesday 2026-11-10 (the shared clock).
MESSAGE = (
    "[10.11.26, 10:30] Frau Schmidt: Hallo zusammen! Hausaufgabe: Arbeitsbuch Seite 24 bis "
    "Freitag. Der Test ist am 20.11.2026. Übung hier: https://example.com/uebung "
    "Ruft mich an: +92 300 1234567. Viele Grüße"
)
AI_ANSWER = {
    "items": [
        {"kind": "homework", "text": "Arbeitsbuch Seite 24", "due": "Freitag"},
        {"kind": "test", "text": "Test über Kapitel 1-3", "due": "20.11.2026"},
        # The AI made this date up: "nächsten Dienstag" is not in the message.
        {"kind": "homework", "text": "Wörter lernen", "due": "nächsten Dienstag"},
    ]
}


def setup(*providers: FakeProvider) -> None:
    app.dependency_overrides[get_providers] = lambda: providers
    app.dependency_overrides[get_limits] = lambda: replace(
        get_limits(), burst_per_minute=1000, user_requests=1000
    )


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    # A fresh cooldown list per test: an outage in one test must not leave "gemini" benched.
    app.dependency_overrides[get_cooldowns] = Cooldowns
    yield
    for dep in (get_providers, get_limits, get_cooldowns):
        app.dependency_overrides.pop(dep, None)


def scan(client: TestClient, text: str = MESSAGE, status: int = 200, **params: Any) -> Any:
    response = client.post("/capture/scan", json={"text": text}, params=params)
    assert response.status_code == status, response.text
    return response.json()


def save(client: TestClient, *items: dict[str, Any], status: int = 201, **params: Any) -> Any:
    response = client.post("/class-tasks", json={"items": list(items)}, params=params)
    assert response.status_code == status, response.text
    return response.json()


def tasks(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/class-tasks", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- Scanning a message ---------------------------------------------------------------------


def test_a_homework_message_becomes_proposed_tasks_with_real_dates_and_saves_nothing(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", AI_ANSWER))

    result = scan(client)

    homework, test, learn = result["items"]
    assert (homework["kind"], homework["title"]) == ("homework", "Arbeitsbuch Seite 24")
    assert (homework["due_text"], homework["due_date"]) == ("Freitag", "2026-11-13")
    assert (test["kind"], test["due_date"]) == ("test", "2026-11-20")
    # A date the AI invented is dropped, so the learner chooses it.
    assert (learn["due_text"], learn["due_date"]) == (None, None)
    # The one link in the message is attached, found without the AI.
    assert result["links"] == ["https://example.com/uebung"]
    assert all(i["url"] == "https://example.com/uebung" for i in result["items"])
    assert result["message"] is None
    assert not any(i["duplicate"] for i in result["items"])
    # Proposing is not saving.
    assert tasks(client, include_done=True) == []


def test_names_numbers_and_links_never_reach_the_ai(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    provider = FakeProvider("gemini", AI_ANSWER)
    setup(provider)

    scan(client)

    (request,) = provider.requests
    for secret in ("Schmidt", "example.com", "1234567", "+92"):
        assert secret not in request.user
    assert "Arbeitsbuch Seite 24 bis Freitag" in request.user


def test_the_learners_timezone_decides_what_today_is(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    # 2026-11-10 09:00 UTC is still Monday 9 November in Pago Pago (UTC-11), so "morgen" moves.
    setup(FakeProvider("gemini", {"items": [{"kind": "test", "text": "Test", "due": "morgen"}]}))
    answer = scan(client, "Test morgen!", tz="Pacific/Pago_Pago")
    assert answer["items"][0]["due_date"] == "2026-11-10"
    answer = scan(client, "Test morgen!", tz="UTC")  # the cached AI answer, resolved for UTC
    assert answer["items"][0]["due_date"] == "2026-11-11"


def test_a_message_with_nothing_to_do_says_so(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", {"items": []}))
    result = scan(client, "Danke und einen schönen Abend!")
    assert result["items"] == []
    assert result["message"] == "No tasks found in this message. You can add one by hand."


def test_a_made_up_kind_becomes_other_and_extra_items_are_cut(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    items = [{"kind": "quiz-night", "text": f"Aufgabe {n}", "due": None} for n in range(12)]
    setup(FakeProvider("gemini", {"items": items}))
    result = scan(client, "Viele Aufgaben")
    assert len(result["items"]) == 8
    assert {i["kind"] for i in result["items"]} == {"other"}


def test_every_kind_the_ai_may_use_is_a_task_kind() -> None:
    assert {k.value for k in TaskKind} == set(CAPTURE_KINDS)
    assert MessageCaptureOut.model_validate({"items": [{"kind": " HOMEWORK ", "text": "x"}]})


def test_several_links_are_all_listed_but_none_is_guessed(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", {"items": [{"kind": "homework", "text": "Übung", "due": None}]}))
    result = scan(client, "Übung: https://a.example/x und https://b.example/y, www.c.example/z.")
    assert result["links"] == [
        "https://a.example/x",
        "https://b.example/y",
        "https://www.c.example/z",
    ]
    assert result["items"][0]["url"] is None


def test_a_task_already_saved_is_flagged_as_a_duplicate(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", AI_ANSWER))
    first = scan(client)
    save(client, {"title": first["items"][0]["title"].upper()})  # case doesn't matter
    again = scan(client)  # the same message: answered from the cache, so it costs nothing
    assert [i["duplicate"] for i in again["items"]] == [True, False, False]


def test_when_the_ai_is_down_the_learner_is_told_and_can_still_add_tasks_by_hand(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", ProviderUnavailable("down")))
    response = client.post("/capture/scan", json={"text": MESSAGE})
    assert response.status_code == 503
    assert "AI help isn't available" in response.json()["detail"]["message"]

    saved = save(client, {"title": "Arbeitsbuch Seite 24", "due_date": "2026-11-13"})
    assert saved[0]["title"] == "Arbeitsbuch Seite 24"


def test_a_message_that_is_too_long_for_the_ai_is_refused_clearly(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", AI_ANSWER))
    response = client.post("/capture/scan", json={"text": "Hausaufgabe " * 400})
    assert response.status_code == 422
    assert "too long" in response.json()["detail"]["message"]


def test_scanning_uses_the_message_scan_allowance(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    setup(FakeProvider("gemini", AI_ANSWER))
    scan(client)
    quota = client.get("/ai/quota").json()
    feature = next(f for f in quota["features"] if f["feature"] == "message_capture")
    assert (feature["used"], feature["label"]) == (1, "message scans")


def test_capture_endpoints_need_a_login(client: TestClient) -> None:
    assert client.post("/capture/scan", json={"text": "x"}).status_code == 401
    assert client.get("/class-tasks").status_code == 401
    assert client.post("/class-tasks", json={"items": []}).status_code == 401


# --- Saving and listing tasks ---------------------------------------------------------------


def test_approved_tasks_are_saved_listed_soonest_first_and_undated_last(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    saved = save(
        client,
        {"title": "Later", "due_date": "2026-11-20", "kind": "test", "due_text": "20.11."},
        {"title": "No date"},
        {"title": "Tomorrow", "due_date": "2026-11-11", "url": "https://example.com/x"},
        {"title": "Overdue", "due_date": "2026-11-08"},
    )
    assert [t["days_left"] for t in saved] == [10, None, 1, -2]
    assert saved[0]["kind"] == "test" and saved[1]["kind"] == "homework"  # homework by default

    assert [t["title"] for t in tasks(client)] == ["Overdue", "Tomorrow", "Later", "No date"]
    assert all(t["done"] is False for t in tasks(client))


def test_the_reminder_time_is_kept_so_the_phone_can_set_it_up_again(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    (task,) = save(
        client,
        {
            "title": "Hausaufgabe",
            "due_date": "2026-11-13",
            "remind_at": "2026-11-12T18:00:00+05:00",
        },
    )
    assert task["remind_at"] == "2026-11-12T13:00:00Z"
    assert tasks(client)[0]["remind_at"] == "2026-11-12T13:00:00Z"


def test_ticking_a_task_off_clears_its_reminder_and_moves_it_to_the_done_list(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    (task,) = save(
        client,
        {"title": "Hausaufgabe", "due_date": "2026-11-13", "remind_at": "2026-11-12T13:00:00Z"},
    )

    done = client.patch(f"/class-tasks/{task['id']}", json={"done": True}).json()
    assert done["done"] is True and done["done_at"] and done["remind_at"] is None
    assert tasks(client) == []
    assert [t["id"] for t in tasks(client, include_done=True)] == [task["id"]]

    clock.advance(days=15)  # finished tasks stay listed for two weeks
    assert tasks(client, include_done=True) == []

    undone = client.patch(f"/class-tasks/{task['id']}", json={"done": False}).json()
    assert undone["done"] is False and undone["done_at"] is None
    assert [t["id"] for t in tasks(client)] == [task["id"]]


def test_a_task_can_be_edited_and_have_its_date_removed(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    (task,) = save(client, {"title": "Hausaufgabe", "due_date": "2026-11-13"})
    edited = client.patch(
        f"/class-tasks/{task['id']}",
        json={"title": "Seite 24", "kind": "deadline", "due_date": None},
    ).json()
    assert (edited["title"], edited["kind"], edited["due_date"]) == ("Seite 24", "deadline", None)
    assert edited["days_left"] is None


def test_bad_input_is_refused(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    (task,) = save(client, {"title": "Hausaufgabe"})
    path = f"/class-tasks/{task['id']}"
    assert client.patch(path, json={"title": None}).status_code == 422
    assert client.patch(path, json={"kind": None}).status_code == 422
    assert client.patch(path, json={"title": "   "}).status_code == 422
    assert client.patch(path, json={"url": "javascript:alert(1)"}).status_code == 422
    assert client.patch(path, json={"url": "https://exa mple.com"}).status_code == 422
    assert client.patch(path, json={"url": "ftp://example.com/x"}).status_code == 422
    save(client, status=422)  # nothing to save
    save(client, *[{"title": f"t{n}"} for n in range(11)], status=422)  # too many at once
    save(client, {"title": "x", "due_date": "13.11."}, status=422)
    save(client, {"title": "x", "kind": "party"}, status=422)
    assert client.get("/class-tasks", params={"tz": "Mars/Base"}).status_code == 422
    assert [t["title"] for t in tasks(client)] == ["Hausaufgabe"]  # all or nothing


def test_one_bad_task_in_a_batch_saves_none_of_them(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    save(client, {"title": "Fine"}, {"title": ""}, status=422)
    assert tasks(client) == []


def test_tasks_can_be_deleted(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    (task,) = save(client, {"title": "Hausaufgabe"})
    assert client.delete(f"/class-tasks/{task['id']}").status_code == 204
    assert tasks(client) == []
    assert client.delete(f"/class-tasks/{task['id']}").status_code == 404


def test_tasks_are_private(client: TestClient, as_user: SwitchUser, clock: Clock) -> None:
    (task,) = save(client, {"title": "Mine"})
    as_user(uuid.uuid4())

    assert tasks(client, include_done=True) == []
    assert client.patch(f"/class-tasks/{task['id']}", json={"done": True}).status_code == 404
    assert client.delete(f"/class-tasks/{task['id']}").status_code == 404
    save(client, {"title": "Theirs"})

    as_user(uuid.UUID(int=0))  # neither of them
    assert tasks(client) == []


# --- On the Today screen --------------------------------------------------------------------


def board(client: TestClient) -> dict[str, Any]:
    response = client.get("/dashboard")
    assert response.status_code == 200, response.text
    return response.json()


def test_urgent_tasks_appear_in_the_plan_with_the_reason_and_undated_ones_do_not(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    save(
        client,
        {"title": "Tomorrow", "due_date": "2026-11-11", "url": "https://example.com/x"},
        {"title": "Next week", "due_date": "2026-11-16"},
        {"title": "Far away", "due_date": "2026-12-24"},
        {"title": "Overdue", "due_date": "2026-11-08"},
        {"title": "No date"},
    )

    result = board(client)

    items = [i for i in result["plan"]["items"] if i["kind"] == "class_task"]
    assert [(i["title"], i["why"]) for i in items] == [
        ("Overdue", "From your class chat: 2 days overdue."),
        ("Tomorrow", "From your class chat: due tomorrow."),
        ("Next week", "From your class chat: due in 6 days."),
    ]
    assert items[1]["url"] == "https://example.com/x" and items[1]["done"] is False
    assert items[1]["class_task_id"] and items[1]["minutes"] == 10
    assert result["class_tasks"] == {"open": 5, "overdue": 1, "due_soon": 1}


def test_a_task_ticked_off_today_stays_in_the_plan_ticked(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    (task,) = save(client, {"title": "Tomorrow", "due_date": "2026-11-11"})
    client.patch(f"/class-tasks/{task['id']}", json={"done": True})

    result = board(client)

    (item,) = [i for i in result["plan"]["items"] if i["kind"] == "class_task"]
    assert item["done"] is True and "ticked off today" in item["why"]
    assert result["class_tasks"] == {"open": 0, "overdue": 0, "due_soon": 0}

    clock.advance(days=1)  # tomorrow it is history
    assert not [i for i in board(client)["plan"]["items"] if i["kind"] == "class_task"]


def test_a_new_learner_has_no_class_tasks(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    result = board(client)
    assert result["class_tasks"] == {"open": 0, "overdue": 0, "due_soon": 0}
    assert not [i for i in result["plan"]["items"] if i["kind"] == "class_task"]
