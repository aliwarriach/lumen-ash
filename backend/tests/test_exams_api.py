import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import SwitchUser
from tests.test_course import add_resource, create_chapter, set_completed
from tests.test_mistakes import log
from tests.test_review_api import TISCH, Clock, add_word, answer, clock, queue

__all__ = ["clock"]  # the fixture, re-used from the review tests

# The frozen clock says it is 10 November 2026.
TODAY = "2026-11-10"


def exam(client: TestClient, days: int = 30, status: int = 201, **extra: Any) -> dict[str, Any]:
    from datetime import date, timedelta

    when = date(2026, 11, 10) + timedelta(days=days)
    body = {"kind": "internal", "title": "Internal test 1", "exam_date": when.isoformat(), **extra}
    response = client.post("/exams", json=body)
    assert response.status_code == status, response.text
    return response.json()


def words(
    client: TestClient, db: Engine, chapter_id: str, n: int, stage: str, tag: str
) -> list[str]:
    """Adds n words to a chapter and sets their stage (reaching a real stage takes weeks)."""
    ids = []
    for i in range(n):
        body = {**TISCH, "german": f"{tag}{i}", "plural": f"{tag}{i}e", "chapter_id": chapter_id}
        ids.append(add_word(client, body)["id"])
    with db.begin() as conn:
        for word_id in ids:
            conn.execute(
                text("UPDATE vocab_words SET stage = :s WHERE id = :i"), {"s": stage, "i": word_id}
            )
    return ids


def course(client: TestClient, db: Engine) -> list[dict[str, Any]]:
    """Six chapters: 1-3 well learned, 4-6 not at all."""
    chapters = [create_chapter(client, n) for n in range(1, 7)]
    for c in chapters:
        n = c["number"]
        words(client, db, c["id"], 3, "usable" if n <= 3 else "new", f"K{n}W")
    return chapters


def detail(client: TestClient, exam_id: str, **params: Any) -> dict[str, Any]:
    response = client.get(f"/exams/{exam_id}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def result(client: TestClient, status: int = 201, **extra: Any) -> dict[str, Any]:
    body = {"kind": "practice", "taken_on": TODAY, "score": 40, "max_score": 50, **extra}
    response = client.post("/exam-results", json=body)
    assert response.status_code == status, response.text
    return response.json()


# --- The Phase 8 example ---


def test_the_app_says_not_ready_yet_focus_on_chapters_4_to_6_and_explains_why(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    created = exam(client, days=30, title="Internal test 1")

    r = detail(client, created["id"])["readiness_detail"]
    assert r["verdict"] == "not_ready"
    assert r["headline"] == "Not ready yet: focus on Chapters 4–6."
    assert r["estimate"] == 50 and r["target"] == 85
    assert [c["number"] for c in r["chapters"] if c["id"] in r["focus_chapter_ids"]] == [4, 5, 6]

    chapters = {c["number"]: c for c in r["chapters"]}
    assert chapters[1]["score"] == 100 and chapters[1]["needs_work"] is False
    assert chapters[5]["score"] == 0 and chapters[5]["needs_work"] is True
    assert chapters[5]["detail"] == "0 of 3 words secure"
    assert chapters[5]["unsecure_words"] == ["der K5W0", "der K5W1", "der K5W2"]
    # The reasons say why, with the learner's numbers.
    assert r["reasons"][0] == "Chapter 4 (Kapitel 4): 0%. 0 of 3 words secure."
    assert r["chapters_with_evidence"] == 6 and r["chapters_total"] == 6


# --- Tests: countdown, scope, validation ---


def test_a_test_has_a_countdown_and_a_phase(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    far = exam(client, days=30, title="Goethe A1", kind="goethe_a1")
    soon = exam(client, days=14, title="Internal")
    today = exam(client, days=0, title="Quiz")
    past = exam(client, days=-3, title="Old test")

    assert (far["days_left"], far["phase"]) == (30, "far")
    assert (soon["days_left"], soon["phase"]) == (14, "revising")
    assert (today["days_left"], today["phase"]) == (0, "today")
    assert (past["days_left"], past["phase"]) == (-3, "past")
    assert far["target_percent"] == 85 and far["whole_course"] is True

    listed = client.get("/exams").json()
    # Upcoming first, soonest first; then the past.
    assert [e["title"] for e in listed] == ["Quiz", "Internal", "Goethe A1", "Old test"]
    assert listed[3]["readiness"] is None and listed[0]["readiness"] is not None


def test_the_countdown_uses_the_learners_local_date(
    client: TestClient, as_user: SwitchUser, clock: Clock
) -> None:
    clock.advance(hours=11)  # 20:00 UTC on the 10th = 01:00 on the 11th in Karachi (UTC+5)
    e = exam(client, days=1)  # the test is on 11 November
    assert client.get(f"/exams/{e['id']}").json()["days_left"] == 1
    assert client.get(f"/exams/{e['id']}", params={"tz": "Asia/Karachi"}).json()["days_left"] == 0


def test_a_test_can_cover_chosen_chapters_or_the_whole_course(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    one, two, three, *_ = course(client, db)
    scoped = exam(client, chapter_ids=[three["id"], one["id"]])
    assert scoped["whole_course"] is False
    assert [c["number"] for c in scoped["chapters"]] == [1, 3]
    readiness = detail(client, scoped["id"])["readiness_detail"]
    assert [c["number"] for c in readiness["chapters"]] == [1, 3]
    assert readiness["verdict"] == "ready"  # chapters 1 and 3 are both fully learned

    whole = client.patch(f"/exams/{scoped['id']}", json={"chapter_ids": []}).json()
    assert whole["whole_course"] is True and whole["chapters"] == []
    assert len(whole["readiness_detail"]["chapters"]) == 6
    del two


def test_deleting_a_chapter_never_turns_a_chapter_test_into_a_whole_course_one(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    one, *_ = course(client, db)
    scoped = exam(client, chapter_ids=[one["id"]])
    assert client.delete(f"/chapters/{one['id']}").status_code == 204

    after = detail(client, scoped["id"])
    assert after["whole_course"] is False and after["chapters"] == []
    assert after["readiness_detail"]["verdict"] == "unknown"
    assert after["readiness_detail"]["headline"] == (
        "Add the chapters this test covers, then the app can judge your readiness."
    )


def test_the_goal_is_the_learners_own(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    chapter = create_chapter(client, 1)
    ids = words(client, db, chapter["id"], 10, "new", "G")
    with db.begin() as conn:
        for word_id in ids[:7]:
            conn.execute(text("UPDATE vocab_words SET stage='usable' WHERE id=:i"), {"i": word_id})
    strict = exam(client)  # default goal: 85%
    easy = exam(client, title="Easy", target_percent=60)
    assert detail(client, strict["id"])["readiness_detail"]["verdict"] == "not_ready"
    assert detail(client, easy["id"])["readiness_detail"]["verdict"] == "ready"


def test_validation(client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock) -> None:
    exam(client, title=" ", status=422)
    exam(client, target_percent=0, status=422)
    exam(client, target_percent=101, status=422)
    exam(client, chapter_ids=[str(uuid.uuid4())], status=422)
    exam(client, kind="driving", status=422)
    e = exam(client)
    assert client.patch(f"/exams/{e['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/exams/{e['id']}", json={"exam_date": None}).status_code == 422
    patched = client.patch(f"/exams/{e['id']}", json={"title": "Renamed", "target_percent": 70})
    assert patched.status_code == 200
    assert (patched.json()["title"], patched.json()["target_percent"]) == ("Renamed", 70)


# --- Evidence: what feeds the chapter scores ---


def test_chapter_scores_come_from_words_grammar_and_workbook(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    chapter = create_chapter(client, 1)
    words(client, db, chapter["id"], 4, "usable", "A")
    words(client, db, chapter["id"], 6, "learning", "B")  # 4 of 10 secure = 40%
    done = add_resource(client, chapter["id"], kind="workbook_exercise", title="Ü1")
    add_resource(client, chapter["id"], kind="workbook_exercise", title="Ü2")
    set_completed(client, done["id"], True)  # 1 of 2 = 50%
    assert (
        client.put(
            "/grammar/patterns/accusative/chapters", json={"chapter_ids": [chapter["id"]]}
        ).status_code
        == 200
    )
    for _ in range(3):  # three wrong answers about the accusative = 0%
        log(client)

    e = exam(client)
    c = detail(client, e["id"])["readiness_detail"]["chapters"][0]
    parts = {p["name"]: p for p in c["parts"]}
    assert parts["vocabulary"]["score"] == 40
    assert parts["grammar"]["score"] == 0
    assert parts["grammar"]["detail"] == "3 wrong out of 3 checked answers"
    assert parts["workbook"]["score"] == 50
    assert c["score"] == (40 * 40 + 0 * 40 + 50 * 20) / 100 == 26
    assert c["weak_patterns"] == ["Accusative case: den, einen"]
    assert c["unsecure_words"][0] == "der B0"  # not yet secure: learning words listed


def test_vocabulary_skill_pools_the_chapters_and_untracked_skills_say_so(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    skills = {
        s["skill"]: s for s in detail(client, exam(client)["id"])["readiness_detail"]["skills"]
    }
    assert skills["vocabulary"]["score"] == 50 and skills["vocabulary"]["tracked"] is True
    assert skills["vocabulary"]["detail"] == "9 of 18 words secure across these chapters"
    assert skills["grammar"]["score"] is None
    for name in ("reading", "listening", "writing", "speaking"):
        assert skills[name]["tracked"] is False and skills[name]["score"] is None
        assert skills[name]["detail"].startswith("Not tracked in the app.")


# --- Results ---


def test_a_practice_result_counts_for_half_and_section_scores_fill_the_untracked_skills(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    e = exam(client)
    before = detail(client, e["id"])["readiness_detail"]
    assert before["estimate"] == 50 and before["practice_score"] is None

    saved = result(
        client,
        exam_id=e["id"],
        title="Modelltest 1",
        score=45,
        max_score=50,
        sections=[
            {"skill": "listening", "score": 18, "max_score": 25},
            {"skill": "reading", "score": 20, "max_score": 25},
        ],
    )
    assert saved["percent"] == 90 and saved["exam_title"] == "Internal test 1"
    assert [(s["skill"], s["percent"]) for s in saved["sections"]] == [
        ("listening", 72),
        ("reading", 80),
    ]

    after = detail(client, e["id"])
    r = after["readiness_detail"]
    assert r["practice_score"] == 90 and r["learning_score"] == 50
    assert r["estimate"] == 70  # half what the app has seen, half the practice test
    assert "Practice tests: 90% on average over your last 1 result." in r["reasons"]
    skills = {s["skill"]: s for s in r["skills"]}
    assert (skills["listening"]["score"], skills["reading"]["score"]) == (72, 80)
    assert skills["listening"]["detail"] == "From the section scores of your recent practice tests."
    assert after["results_count"] == 1 and after["results"][0]["id"] == saved["id"]


def test_only_the_three_most_recent_practice_tests_count(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    create_chapter(client, 1)
    e = exam(client)
    for day, score in (
        ("2026-11-01", 0),
        ("2026-11-05", 50),
        ("2026-11-06", 50),
        ("2026-11-07", 50),
    ):
        result(client, exam_id=e["id"], taken_on=day, score=score, max_score=100)
    r = detail(client, e["id"])["readiness_detail"]
    assert r["practice_score"] == 50  # the 0% test from the 1st is no longer counted
    assert r["verdict"] == "not_ready" and r["learning_score"] is None
    assert r["headline"] == "Not ready yet: focus on Chapter 1."


def test_a_test_that_is_not_tied_to_any_exam_counts_for_every_exam(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    create_chapter(client, 1)
    a, b = exam(client, title="A"), exam(client, title="B")
    result(client, score=80, max_score=100)  # a loose practice test
    result(client, exam_id=b["id"], score=20, max_score=100)  # tied to B only
    assert detail(client, a["id"])["readiness_detail"]["practice_score"] == 80
    assert detail(client, b["id"])["readiness_detail"]["practice_score"] == 50


def test_chapters_where_marks_were_lost_are_remembered(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    one, two, *_ = course(client, db)
    e = exam(client)
    result(client, exam_id=e["id"], title="Modelltest 2", weak_chapter_ids=[two["id"]])
    chapters = {c["number"]: c for c in detail(client, e["id"])["readiness_detail"]["chapters"]}
    assert chapters[2]["lost_marks_in"] == ["Modelltest 2 on 10 Nov"]
    assert chapters[1]["lost_marks_in"] == []
    del one


def test_the_real_result_is_recorded_after_the_test(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    past = exam(client, days=-2, title="Internal test 1")
    assert past["phase"] == "past" and past["readiness"] is None
    real = result(client, exam_id=past["id"], kind="exam", score=88, max_score=100)
    assert real["kind"] == "exam" and real["percent"] == 88

    after = detail(client, past["id"])
    assert after["readiness_detail"] is None and after["revision"] is None
    assert [r["percent"] for r in after["results"]] == [88]
    # A real result isn't practice, so it never changes another test's readiness.
    create_chapter(client, 1)
    other = exam(client, title="Goethe", kind="goethe_a1")
    assert detail(client, other["id"])["readiness_detail"]["practice_score"] is None


def test_result_validation(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    result(client, status=422, score=60, max_score=50)
    result(client, status=422, score=-1)
    result(client, status=422, max_score=0)
    result(client, status=422, kind="homework")
    two = [{"skill": "listening", "score": 5, "max_score": 25}] * 2
    result(client, status=422, sections=two)
    result(client, status=422, sections=[{"skill": "listening", "score": 30, "max_score": 25}])
    result(client, status=422, weak_chapter_ids=[str(uuid.uuid4())])
    result(client, status=404, exam_id=str(uuid.uuid4()))
    assert client.get("/exam-results").json() == []


def test_results_can_be_listed_and_deleted_and_survive_their_test(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    e = exam(client)
    mine = result(client, exam_id=e["id"], taken_on="2026-11-02")
    loose = result(client, taken_on="2026-11-08")
    listed = client.get("/exam-results").json()
    assert [r["id"] for r in listed] == [loose["id"], mine["id"]]  # newest first
    assert listed[1]["exam_title"] == "Internal test 1" and listed[0]["exam_title"] is None
    only = client.get("/exam-results", params={"exam_id": e["id"]}).json()
    assert [r["id"] for r in only] == [mine["id"]]

    assert client.delete(f"/exams/{e['id']}").status_code == 204
    kept = client.get("/exam-results").json()
    assert {r["id"] for r in kept} == {mine["id"], loose["id"]}
    assert all(r["exam_id"] is None for r in kept)

    assert client.delete(f"/exam-results/{mine['id']}").status_code == 204
    assert client.delete(f"/exam-results/{mine['id']}").status_code == 404
    assert len(client.get("/exam-results").json()) == 1


# --- The revision plan ---


def test_nothing_changes_until_two_weeks_before_the_test(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    far = detail(client, exam(client, days=30)["id"])
    assert far["revision"] == {"phase": "far", "schedule": []}


def test_each_day_gets_one_weak_chapter_with_more_time_as_the_test_gets_closer(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)  # chapters 4, 5 and 6 need work
    revision = detail(client, exam(client, days=5)["id"])["revision"]

    assert revision["phase"] == "revising"
    plan = [(d["days_left"], d["chapter"]["number"], d["minutes"]) for d in revision["schedule"]]
    # Course order [4, 5, 6] rotating by days left, so no chapter is skipped for long.
    assert plan == [(5, 6, 15), (4, 5, 15), (3, 4, 20), (2, 6, 20), (1, 5, 20)]
    first = revision["schedule"][0]
    assert first["day"] == TODAY
    assert first["why"] == (
        "Internal test 1 is in 5 days. Chapter 6 is at 0%: 0 of 3 words secure."
    )
    assert first["words"] == ["der K6W0", "der K6W1", "der K6W2"]


def test_a_chapter_with_no_evidence_is_still_scheduled_and_says_what_to_do(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    create_chapter(client, 1)
    first = detail(client, exam(client, days=10)["id"])["revision"]["schedule"][0]
    assert first["why"] == (
        "Internal test 1 is in 10 days. Chapter 1 has no evidence yet: add its words and "
        "answer review cards."
    )
    assert first["minutes"] == 10


def test_with_nothing_to_work_on_there_is_nothing_to_schedule(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    chapter = create_chapter(client, 1)
    words(client, db, chapter["id"], 3, "mastered", "Z")
    d = detail(client, exam(client, days=5)["id"])
    assert d["readiness_detail"]["verdict"] == "ready" and d["revision"]["schedule"] == []


# --- It feeds the daily plan and the dashboard ---


def test_the_dashboard_counts_down_to_the_next_test_and_says_whether_you_are_ready(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    board = client.get("/dashboard").json()
    assert board["test"]["next"] is None and "No test coming up" in board["test"]["message"]

    course(client, db)
    exam(client, days=-5, title="Past test")  # passed tests are ignored
    exam(client, days=40, title="Goethe A1", kind="goethe_a1")
    exam(client, days=20, title="Internal test 1")

    nxt = client.get("/dashboard").json()["test"]["next"]
    assert (nxt["title"], nxt["days_left"], nxt["kind"]) == ("Internal test 1", 20, "internal")
    assert nxt["headline"] == "Not ready yet: focus on Chapters 4–6."
    assert [c["number"] for c in nxt["focus"]] == [4, 5, 6]
    assert nxt["target_percent"] == 85 and nxt["verdict"] == "not_ready"


def test_revision_for_a_close_test_joins_todays_plan_and_is_ticked_after_enough_reviews(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    # Chapter 1 is the weak one (and its words are first in the queue); 2 and 3 are learned.
    one, two, three = (create_chapter(client, n) for n in (1, 2, 3))
    weak_words = set(words(client, db, one["id"], 3, "new", "K1W"))
    words(client, db, two["id"], 3, "usable", "K2W")
    words(client, db, three["id"], 3, "usable", "K3W")
    exam(client, days=5)

    plan = client.get("/dashboard").json()["plan"]
    item = next(i for i in plan["items"] if i["kind"] == "exam")
    assert item["title"] == "Revise Chapter 1: Kapitel 1"
    assert item["why"] == "Internal test 1 is in 5 days. Chapter 1 is at 0%: 0 of 3 words secure."
    assert (item["minutes"], item["done"], item["chapter_id"]) == (15, False, one["id"])
    assert item["words"] == ["der K1W0", "der K1W1", "der K1W2"]

    done = 0
    for card in queue(client)["cards"]:
        if card["word"] and card["word"]["id"] in weak_words and done < 5:
            answer(client, card, rating=3, text="der K1W0", article="der", plural="x")
            done += 1
            if done == 4:  # one short of enough: not ticked yet
                mid = next(
                    i
                    for i in client.get("/dashboard").json()["plan"]["items"]
                    if i["kind"] == "exam"
                )
                assert mid["done"] is False
    assert done == 5
    after = next(i for i in client.get("/dashboard").json()["plan"]["items"] if i["kind"] == "exam")
    assert after["done"] is True


def test_in_the_last_three_days_revision_goes_ahead_of_grammar(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    log(client)  # a weak grammar pattern, so there is a grammar item
    exam(client, days=2)
    kinds = [i["kind"] for i in client.get("/dashboard").json()["plan"]["items"]]
    assert kinds.index("exam") < kinds.index("grammar")

    other = exam(client, days=9, title="Later")
    del other


def test_a_test_more_than_two_weeks_away_adds_no_revision_item(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    course(client, db)
    exam(client, days=30)
    board = client.get("/dashboard").json()
    assert "exam" not in [i["kind"] for i in board["plan"]["items"]]
    assert board["test"]["next"]["days_left"] == 30


# --- Privacy ---


def test_one_learner_cannot_see_or_change_anothers_tests_or_results(
    client: TestClient, as_user: SwitchUser, db: Engine, clock: Clock
) -> None:
    alice, bob = uuid.uuid4(), uuid.uuid4()
    as_user(alice)
    chapter = create_chapter(client, 1)
    e = exam(client)
    mine = result(client, exam_id=e["id"])

    as_user(bob)
    assert client.get("/exams").json() == [] and client.get("/exam-results").json() == []
    assert client.get(f"/exams/{e['id']}").status_code == 404
    assert client.patch(f"/exams/{e['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/exams/{e['id']}").status_code == 404
    assert client.delete(f"/exam-results/{mine['id']}").status_code == 404
    result(client, status=404, exam_id=e["id"])  # can't attach a result to Alice's test
    result(client, status=422, weak_chapter_ids=[chapter["id"]])  # or use her chapters
    exam(client, status=422, chapter_ids=[chapter["id"]])
    assert client.get("/dashboard").json()["test"]["next"] is None


def test_the_test_endpoints_require_login(client: TestClient) -> None:
    assert client.get("/exams").status_code == 401
    assert client.post("/exam-results", json={}).status_code == 401
