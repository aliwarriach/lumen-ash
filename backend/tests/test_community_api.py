import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.community.hub import Hub
from app.community.router import get_hub, get_rules
from app.community.schemas import MAX_BODY
from app.community.service import (
    NAME_LOCKED,
    NAME_TAKEN,
    NEED_NAME,
    NOT_YOURS,
    REPLY_GONE,
    CommunityRules,
)
from app.main import app
from tests.conftest import SwitchUser

ALI = uuid.uuid4()
SARA = uuid.uuid4()
OMAR = uuid.uuid4()


def use_rules(per_minute: int = 1000, moderators: tuple[uuid.UUID, ...] = ()) -> None:
    """`as_user` gives each person the email `<id>@example.com`."""
    emails = frozenset(f"{m}@example.com" for m in moderators)
    app.dependency_overrides[get_rules] = lambda: CommunityRules(per_minute, emails)


@pytest.fixture(autouse=True)
def fresh_chat() -> Iterator[Hub]:
    hub = Hub()
    app.dependency_overrides[get_hub] = lambda: hub
    use_rules()
    yield hub
    for dep in (get_hub, get_rules):
        app.dependency_overrides.pop(dep, None)


def name(client: TestClient, display_name: str, status: int = 200) -> Any:
    response = client.put("/community/me", json={"display_name": display_name})
    assert response.status_code == status, response.text
    return response.json()


def post(
    client: TestClient,
    body: str,
    status: int = 201,
    message_id: uuid.UUID | None = None,
    reply_to: str | None = None,
) -> Any:
    payload = {"id": str(message_id or uuid.uuid4()), "body": body, "reply_to_id": reply_to}
    response = client.post("/community/messages", json=payload)
    assert response.status_code == status, response.text
    return response.json()


def page(client: TestClient, **params: Any) -> Any:
    response = client.get("/community/messages", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def changes(client: TestClient, after: int, **params: Any) -> Any:
    response = client.get("/community/changes", params={"after": after, **params})
    assert response.status_code == 200, response.text
    return response.json()


def delete(client: TestClient, message_id: str, status: int = 200) -> Any:
    response = client.delete(f"/community/messages/{message_id}")
    assert response.status_code == status, response.text
    return response.json()


def join(client: TestClient, as_user: SwitchUser, user_id: uuid.UUID, display_name: str) -> None:
    as_user(user_id)
    name(client, display_name)


# --- Names ---------------------------------------------------------------------------------------


def test_the_chat_needs_a_login(client: TestClient) -> None:
    assert client.get("/community/me").status_code == 401
    assert client.get("/community/messages").status_code == 401
    assert client.get("/community/changes", params={"after": 0}).status_code == 401
    body = {"id": str(uuid.uuid4()), "body": "Hallo"}
    assert client.post("/community/messages", json=body).status_code == 401


def test_a_person_has_no_name_until_they_choose_one_and_cannot_post_before(
    client: TestClient, as_user: SwitchUser
) -> None:
    as_user(ALI)
    me = client.get("/community/me").json()
    assert me["display_name"] is None
    assert me["user_id"] == str(ALI)
    assert (me["moderator"], me["max_message_chars"]) == (False, MAX_BODY)

    assert post(client, "Hallo", status=409)["detail"] == NEED_NAME

    assert name(client, "  Ali_Khan ")["display_name"] == "Ali_Khan"  # surrounding spaces dropped
    assert post(client, "Hallo")["author_name"] == "Ali_Khan"


def test_two_people_cannot_have_the_same_name_however_it_is_typed(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Müller")
    as_user(SARA)
    for same in ("Müller", "MÜLLER", "müller", "Müller"):  # the last: u + combining dots
        assert name(client, same, status=409)["detail"] == NAME_TAKEN
    name(client, "Sara")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        " ",
        "Al",
        "x" * 21,
        "---",
        "___",
        "123",
        "​​​",
        "\n\n",
        "Ali Khan",
        "Ali.K",
        "Ali!",
        "Аli",  # first letter is Cyrillic: looks like "Ali"
        "admin",
        "Admin_",
        "TEACHER",
        "Mod",
    ],
)
def test_names_that_are_too_short_too_long_or_invisible_are_refused(
    client: TestClient, as_user: SwitchUser, bad: str
) -> None:
    as_user(ALI)
    name(client, bad, status=422)


def test_a_username_is_fixed_once_chosen(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    post(client, "Hallo")
    assert name(client, "Ali_K", status=403)["detail"] == NAME_LOCKED
    assert name(client, "ALI", status=403)["detail"] == NAME_LOCKED  # even just the case
    assert [m["author_name"] for m in page(client)["items"]] == ["Ali"]


def test_a_moderator_can_still_change_their_own_username(
    client: TestClient, as_user: SwitchUser
) -> None:
    use_rules(moderators=(OMAR,))
    join(client, as_user, OMAR, "Omar")
    post(client, "Hallo")
    name(client, "Omar_Mod")
    assert [m["author_name"] for m in page(client)["items"]] == ["Omar_Mod"]


# --- Posting and reading -------------------------------------------------------------------------


def test_everyone_sees_everyones_messages_in_order_and_nobodys_email(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    first = post(client, "  Was bedeutet 'doch'?  ")
    join(client, as_user, SARA, "Sara")
    second = post(client, "Es widerspricht einer Verneinung.\nZum Beispiel:\n- Doch!")

    assert first["body"] == "Was bedeutet 'doch'?"  # trimmed
    assert second["body"].count("\n") == 2  # line breaks kept
    assert first["seq"] < second["seq"]

    as_user(OMAR)  # no name yet: reading doesn't need one
    response = client.get("/community/messages")
    got = response.json()
    assert [(m["author_name"], m["author_id"]) for m in got["items"]] == [
        ("Ali", str(ALI)),
        ("Sara", str(SARA)),
    ]
    assert got["has_more"] is False
    assert "@example.com" not in response.text


@pytest.mark.parametrize("bad", ["", "   ", "\n\t ", "\x00", "​", "x" * (MAX_BODY + 1)])
def test_empty_invisible_and_overlong_messages_are_refused(
    client: TestClient, as_user: SwitchUser, bad: str
) -> None:
    join(client, as_user, ALI, "Ali")
    post(client, bad, status=422)
    assert page(client)["items"] == []


def test_characters_the_database_or_the_screen_cannot_take_are_removed(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    # A NUL would make Postgres refuse the row; the others are invisible.
    assert post(client, "Gu\x00ten​ Tag\x07 😀 ß")["body"] == "Guten Tag 😀 ß"
    assert len(post(client, "x" * MAX_BODY)["body"]) == MAX_BODY


def test_a_send_that_is_retried_posts_once(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    message_id = uuid.uuid4()
    first = post(client, "Hallo", message_id=message_id)
    again = post(client, "Hallo", message_id=message_id)
    assert again == first
    assert len(page(client)["items"]) == 1

    # Someone else can't take over an id that is in use.
    join(client, as_user, SARA, "Sara")
    post(client, "Meins", message_id=message_id, status=409)
    assert page(client)["items"][0]["body"] == "Hallo"


def test_older_messages_load_a_page_at_a_time(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    for n in range(1, 8):
        post(client, f"m{n}")

    latest = page(client, limit=3)
    assert [m["body"] for m in latest["items"]] == ["m5", "m6", "m7"]
    assert latest["has_more"] is True

    older = page(client, limit=3, before=latest["items"][0]["seq"])
    assert [m["body"] for m in older["items"]] == ["m2", "m3", "m4"]
    assert older["has_more"] is True

    oldest = page(client, limit=3, before=older["items"][0]["seq"])
    assert [m["body"] for m in oldest["items"]] == ["m1"]
    assert oldest["has_more"] is False


# --- Keeping up ----------------------------------------------------------------------------------


def test_changes_bring_what_was_posted_and_deleted_since_the_phone_last_asked(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    old = post(client, "alt")
    cursor = page(client)["rev"]
    assert changes(client, cursor) == {"items": [], "rev": cursor, "has_more": False}

    new = post(client, "neu")
    got = changes(client, cursor)
    assert [m["id"] for m in got["items"]] == [new["id"]]
    assert got["rev"] == new["rev"] > cursor
    cursor = got["rev"]

    # Deleting an old message is a change too, and comes after everything seen so far.
    delete(client, old["id"])
    got = changes(client, cursor)
    assert [(m["id"], m["deleted"], m["body"]) for m in got["items"]] == [(old["id"], True, None)]
    assert got["rev"] > cursor
    assert changes(client, got["rev"])["items"] == []


def test_a_phone_far_behind_is_told_there_is_more_than_fits(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    for n in range(5):
        post(client, f"m{n}")
    got = changes(client, 0, limit=3)
    assert [m["body"] for m in got["items"]] == ["m0", "m1", "m2"]
    assert got["has_more"] is True
    rest = changes(client, got["rev"], limit=3)
    assert [m["body"] for m in rest["items"]] == ["m3", "m4"]
    assert rest["has_more"] is False


# --- Deleting ------------------------------------------------------------------------------------


def test_deleting_erases_the_text_and_only_the_author_or_a_moderator_may(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    use_rules(moderators=(OMAR,))
    join(client, as_user, ALI, "Ali")
    mine = post(client, "Meine Telefonnummer ist 0300 1234567")
    other = post(client, "Noch eine Nachricht")

    as_user(SARA)
    assert delete(client, mine["id"], status=403)["detail"] == NOT_YOURS
    delete(client, str(uuid.uuid4()), status=404)

    as_user(ALI)
    gone = delete(client, mine["id"])
    assert (gone["deleted"], gone["body"]) == (True, None)
    assert delete(client, mine["id"])["rev"] == gone["rev"]  # twice changes nothing
    with db.connect() as conn:
        stored = conn.execute(
            text("SELECT body, deleted_by FROM community_messages WHERE id = :id"),
            {"id": mine["id"]},
        ).one()
    assert stored == ("", ALI)  # the text is not kept

    as_user(OMAR)
    assert client.get("/community/me").json()["moderator"] is True
    assert delete(client, other["id"])["deleted"] is True
    assert [m["deleted"] for m in page(client)["items"]] == [True, True]


# --- Replies -------------------------------------------------------------------------------------


def test_an_answer_shows_what_it_answers(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    question = post(client, "Wann benutzt man 'den'?\n" + "sehr lang " * 30)
    join(client, as_user, SARA, "Sara")
    answer = post(client, "Im Akkusativ, maskulin.", reply_to=question["id"])

    reply = answer["reply_to"]
    assert (reply["id"], reply["author_name"]) == (question["id"], "Ali")
    assert reply["excerpt"].startswith("Wann benutzt man 'den'? sehr lang")  # one line
    assert len(reply["excerpt"]) <= 140 and reply["excerpt"].endswith("…")
    assert question["reply_to"] is None

    # The question is deleted: the answer stays, without the quoted text.
    as_user(ALI)
    delete(client, question["id"])
    shown = page(client)["items"][1]
    assert (shown["id"], shown["reply_to"]["excerpt"]) == (answer["id"], None)

    # And it can't be answered any more.
    assert post(client, "?", reply_to=question["id"], status=404)["detail"] == REPLY_GONE
    post(client, "?", reply_to=str(uuid.uuid4()), status=404)


# --- Limits --------------------------------------------------------------------------------------


def test_posting_too_fast_is_refused_but_a_retry_of_a_sent_message_is_not(
    client: TestClient, as_user: SwitchUser
) -> None:
    use_rules(per_minute=3)
    join(client, as_user, ALI, "Ali")
    last = uuid.uuid4()
    post(client, "1")
    post(client, "2")
    post(client, "3", message_id=last)

    response = client.post("/community/messages", json={"id": str(uuid.uuid4()), "body": "4"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "15"
    assert "Wait a few seconds" in response.json()["detail"]

    assert post(client, "3", message_id=last)["body"] == "3"  # already saved: not a new post
    assert len(page(client)["items"]) == 3

    # One person's flood doesn't stop anyone else.
    join(client, as_user, SARA, "Sara")
    post(client, "Hallo")


# --- Ask the Community ---------------------------------------------------------------------------


def ask(
    client: TestClient, attachment: Any, status: int = 201, body: str = "Wie sagt man das?"
) -> Any:
    payload = {"id": str(uuid.uuid4()), "body": body, "attachment": attachment}
    response = client.post("/community/messages", json=payload)
    assert response.status_code == status, response.text
    return response.json()


def test_a_question_can_carry_the_item_it_is_about(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    word = {"kind": "word", "title": "der Tisch", "lines": ["table", "Plural: die Tische"]}
    sent = ask(client, word)
    assert sent["attachment"] == word

    as_user(SARA)  # everyone sees the card, on the page and in the changes
    assert page(client)["items"][-1]["attachment"] == word
    assert changes(client, 0)["items"][-1]["attachment"] == word
    # An ordinary message has none.
    join(client, as_user, SARA, "Sara")
    assert post(client, "Hallo")["attachment"] is None


def test_a_shared_item_is_tidied_and_kept_small(client: TestClient, as_user: SwitchUser) -> None:
    join(client, as_user, ALI, "Ali")
    messy = {
        "kind": "exercise",
        "title": "  Ergänze​   die Sätze \n",
        "lines": ["", "Ich ___ aus Pakistan.\x00", "x" * 400],
    }
    got = ask(client, messy)["attachment"]
    assert got["title"] == "Ergänze die Sätze"
    assert got["lines"][0] == "Ich ___ aus Pakistan."
    assert len(got["lines"]) == 2 and len(got["lines"][1]) == 300 and got["lines"][1].endswith("…")
    assert len(ask(client, {"kind": "lesson", "title": "T" * 500})["attachment"]["title"]) == 120


def test_a_shared_item_must_be_a_known_kind_with_a_title_and_few_lines(
    client: TestClient, as_user: SwitchUser
) -> None:
    join(client, as_user, ALI, "Ali")
    ask(client, {"kind": "video", "title": "x"}, status=422)
    ask(client, {"kind": "word", "title": "   "}, status=422)
    ask(client, {"kind": "word", "title": "x", "lines": ["a"] * 7}, status=422)
    # The question itself is still required.
    ask(client, {"kind": "word", "title": "der Tisch"}, status=422, body="  ")


def test_deleting_a_question_also_erases_its_shared_item(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    join(client, as_user, ALI, "Ali")
    sent = ask(client, {"kind": "resource", "title": "Hörtext 2", "lines": ["Kapitel 4, S. 24"]})
    gone = delete(client, sent["id"])
    assert gone["attachment"] is None
    with db.connect() as conn:
        stored = conn.execute(
            text("SELECT attachment FROM community_messages WHERE id = :id"), {"id": sent["id"]}
        ).scalar_one()
    assert stored is None
