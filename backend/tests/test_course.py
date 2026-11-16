import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import SwitchUser


def create_chapter(client: TestClient, number: int = 1, **extra: Any) -> dict[str, Any]:
    response = client.post(
        "/chapters", json={"number": number, "title": f"Kapitel {number}", **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_resource(client: TestClient, chapter_id: str, **extra: Any) -> dict[str, Any]:
    body = {"kind": "audio", "title": "Hörtext 1", **extra}
    response = client.post(f"/chapters/{chapter_id}/resources", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def set_completed(client: TestClient, resource_id: str, completed: bool) -> dict[str, Any]:
    response = client.patch(f"/resources/{resource_id}", json={"completed": completed})
    assert response.status_code == 200, response.text
    return response.json()


def test_create_and_list_chapters_in_order(client: TestClient, as_user: SwitchUser) -> None:
    create_chapter(client, 2)
    create_chapter(client, 1, topics=["sich vorstellen", "Zahlen"])

    chapters = client.get("/chapters").json()

    assert [c["number"] for c in chapters] == [1, 2]
    assert chapters[0]["topics"] == ["sich vorstellen", "Zahlen"]
    assert chapters[0]["progress"] == {"total": 0, "completed": 0, "status": "not_started"}


def test_duplicate_chapter_number_conflicts(client: TestClient, as_user: SwitchUser) -> None:
    create_chapter(client, 1)
    response = client.post("/chapters", json={"number": 1, "title": "Again"})
    assert response.status_code == 409


def test_two_users_can_use_the_same_chapter_number(client: TestClient, as_user: SwitchUser) -> None:
    create_chapter(client, 1)
    as_user(uuid.uuid4())
    create_chapter(client, 1)


def test_progress_follows_resource_completion(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client)
    first = add_resource(client, chapter["id"])
    second = add_resource(client, chapter["id"], kind="workbook_exercise", reference="S. 24, Ü 3")
    assert [first["position"], second["position"]] == [0, 1]

    def progress() -> dict[str, Any]:
        return client.get(f"/chapters/{chapter['id']}").json()["progress"]

    assert progress()["status"] == "not_started"

    done = set_completed(client, first["id"], True)
    assert done["completed_at"] is not None
    assert progress() == {"total": 2, "completed": 1, "status": "in_progress"}

    set_completed(client, second["id"], True)
    assert progress()["status"] == "completed"
    listed = client.get("/chapters").json()[0]["progress"]
    assert listed == {"total": 2, "completed": 2, "status": "completed"}

    undone = set_completed(client, second["id"], False)
    assert undone["completed_at"] is None
    assert progress()["status"] == "in_progress"


def test_completing_twice_keeps_first_timestamp(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client)
    resource = add_resource(client, chapter["id"])
    first = set_completed(client, resource["id"], True)["completed_at"]
    assert set_completed(client, resource["id"], True)["completed_at"] == first


def test_update_chapter_fields(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client, notes="old")
    response = client.patch(
        f"/chapters/{chapter['id']}", json={"title": "  Guten Tag  ", "notes": None}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Guten Tag"
    assert response.json()["notes"] is None


def test_update_rejects_null_for_required_fields(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client)
    response = client.patch(f"/chapters/{chapter['id']}", json={"title": None})
    assert response.status_code == 422


def test_renumbering_onto_existing_chapter_conflicts(
    client: TestClient, as_user: SwitchUser
) -> None:
    create_chapter(client, 1)
    second = create_chapter(client, 2)
    response = client.patch(f"/chapters/{second['id']}", json={"number": 1})
    assert response.status_code == 409


def test_resource_url_must_be_http(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client)
    response = client.post(
        f"/chapters/{chapter['id']}/resources",
        json={"kind": "video", "title": "Video", "url": "javascript:alert(1)"},
    )
    assert response.status_code == 422

    ok = add_resource(client, chapter["id"], url="https://www.allango.net/some/page")
    assert ok["url"] == "https://www.allango.net/some/page"


def test_deleting_chapter_deletes_its_resources(client: TestClient, as_user: SwitchUser) -> None:
    chapter = create_chapter(client)
    resource = add_resource(client, chapter["id"])

    assert client.delete(f"/chapters/{chapter['id']}").status_code == 204
    assert client.get(f"/chapters/{chapter['id']}").status_code == 404
    assert client.patch(f"/resources/{resource['id']}", json={"title": "x"}).status_code == 404


def test_users_cannot_see_or_change_each_others_data(
    client: TestClient, as_user: SwitchUser
) -> None:
    chapter = create_chapter(client)
    resource = add_resource(client, chapter["id"])

    as_user(uuid.uuid4())
    # The other learner gets the starter course, but none of this learner's chapters.
    assert chapter["id"] not in [c["id"] for c in client.get("/chapters").json()]
    assert client.get(f"/chapters/{chapter['id']}").status_code == 404
    assert client.patch(f"/chapters/{chapter['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/chapters/{chapter['id']}").status_code == 404
    new_resource = {"kind": "audio", "title": "x"}
    assert client.post(f"/chapters/{chapter['id']}/resources", json=new_resource).status_code == 404
    assert client.patch(f"/resources/{resource['id']}", json={"completed": True}).status_code == 404
    assert client.delete(f"/resources/{resource['id']}").status_code == 404


def test_chapter_endpoints_require_login(client: TestClient) -> None:
    assert client.get("/chapters").status_code == 401


def test_new_learner_starts_with_the_allango_course(
    client: TestClient, as_user: SwitchUser
) -> None:
    from collections import Counter

    from app.course.import_links import bundled_items

    expected = Counter(item.chapter for item in bundled_items())
    chapters = client.get("/chapters").json()

    assert [c["number"] for c in chapters] == sorted(expected)
    assert [c["title"] for c in chapters] == [f"Kapitel {n}" for n in sorted(expected)]
    assert [c["progress"]["total"] for c in chapters] == [expected[c["number"]] for c in chapters]

    detail = client.get(f"/chapters/{chapters[0]['id']}").json()
    first = detail["resources"][0]
    assert first["kind"] == "audio"
    assert first["reference"] == "S. 8"
    assert first["url"].startswith("https://www.allango.net/")

    # Asking again never adds the course a second time.
    again = client.get("/chapters").json()
    assert [c["progress"]["total"] for c in again] == [c["progress"]["total"] for c in chapters]


def test_learner_with_their_own_chapters_is_not_given_the_course(
    client: TestClient, as_user: SwitchUser
) -> None:
    create_chapter(client, 7)

    assert [c["number"] for c in client.get("/chapters").json()] == [7]


def test_link_list_lines_are_read_and_bad_ones_named() -> None:
    from app.course.import_links import parse_file

    good = "8 | audio | Netzwerk-A1 Track 1.2 - 01-2a Hallo! | https://www.allango.net/p?page=8"
    items, problems = parse_file(f"# comment\n\n{good}\n")
    assert problems == []
    assert (items[0].chapter, items[0].page, items[0].title) == (1, 8, "Track 1.2 - 01-2a Hallo!")

    _, problems = parse_file(
        "x | audio | t - 01-1a | https://a.b\n"
        "1 | podcast | t - 01-1a | https://a.b\n"
        "1 | audio | no code here | https://a.b\n"
        "1 | audio | t - 01-1a | http://a.b\n"
    )
    assert len(problems) == 4


def test_review_codes_and_plattform_pages_land_in_the_right_chapter() -> None:
    from app.course.import_links import parse_file

    base = "https://www.allango.net/p?page="
    items, problems = parse_file(
        f"97 | audio | Netzwerk-A1 AB Track 1.32 - 02-R1 Das kann ich 1, 2 | {base}97\n"
        f"106 | audio | Netzwerk-A1 AB Track 1.40 - 03-9a Hamburg | {base}106\n"
        f"113 | audio | Netzwerk-A1 AB Track 1.41 - Plattform 1-3 0 | {base}113\n"
        f"115 | audio | Netzwerk-A1 AB Track 1.48 - Plattform 1-6a | {base}115\n"
        f"117 | audio | Netzwerk-A1 AB Track 1.49 - 04-3a Frühstück | {base}117\n"
    )
    assert problems == []
    assert [i.chapter for i in items] == [2, 3, 3, 3, 4]

    # A Plattform line with nothing before it has no chapter to join.
    _, problems = parse_file(f"113 | audio | Netzwerk-A1 AB Track 1.41 - Plattform 1-3 0 | {base}1")
    assert len(problems) == 1


def test_workbook_items_are_labelled_as_workbook_pages(
    client: TestClient, as_user: SwitchUser
) -> None:
    chapters = client.get("/chapters").json()
    chapter_two = next(c for c in chapters if c["number"] == 2)
    resources = client.get(f"/chapters/{chapter_two['id']}").json()["resources"]

    references = {r["reference"] for r in resources}
    assert "S. 17" in references  # the textbook
    assert "AB S. 91" in references  # the workbook, same page numbers further on
