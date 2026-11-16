import uuid
from datetime import date, timedelta

from app.exams.readiness import ChapterEvidence, ChapterReadiness, chapter_readiness
from app.exams.revision import (
    Phase,
    countdown_text,
    minutes_for,
    phase_for,
    revision_plan,
    why_chapter,
)

TODAY = date(2026, 11, 10)


def weak(number: int) -> ChapterReadiness:
    return chapter_readiness(
        ChapterEvidence(uuid.uuid4(), number, f"K{number}", words_total=10, words_secure=2), 85
    )


def test_phases_by_days_left() -> None:
    assert [phase_for(d) for d in (30, 15, 14, 1, 0, -1)] == [
        Phase.FAR,
        Phase.FAR,
        Phase.REVISING,
        Phase.REVISING,
        Phase.TODAY,
        Phase.PAST,
    ]


def test_more_minutes_as_the_test_gets_closer() -> None:
    assert [minutes_for(d) for d in (15, 14, 8, 7, 4, 3, 1)] == [0, 10, 10, 15, 15, 20, 20]


def test_revision_starts_exactly_fourteen_days_out() -> None:
    focus = [weak(1), weak(2)]
    assert revision_plan(TODAY, TODAY + timedelta(days=15), focus).schedule == []
    plan = revision_plan(TODAY, TODAY + timedelta(days=14), focus)
    assert len(plan.schedule) == 14 and plan.today is plan.schedule[0]
    assert plan.schedule[0].days_left == 14 and plan.schedule[-1].days_left == 1
    assert plan.schedule[-1].day == TODAY + timedelta(days=13)  # the day before the test


def test_the_rotation_visits_every_weak_chapter_and_ignores_input_order() -> None:
    chapters = [weak(6), weak(4), weak(5)]
    plan = revision_plan(TODAY, TODAY + timedelta(days=6), chapters)
    seen = [d.chapter.number for d in plan.schedule]
    assert set(seen[:3]) == {4, 5, 6}  # no chapter waits more than three days
    shuffled = revision_plan(TODAY, TODAY + timedelta(days=6), list(reversed(chapters)))
    assert [d.chapter.number for d in shuffled.schedule] == seen


def test_no_revision_on_the_day_after_the_day_or_with_nothing_to_work_on() -> None:
    assert revision_plan(TODAY, TODAY, [weak(1)]).schedule == []
    assert revision_plan(TODAY, TODAY - timedelta(days=1), [weak(1)]).schedule == []
    assert revision_plan(TODAY, TODAY + timedelta(days=5), []).schedule == []
    assert revision_plan(TODAY, TODAY + timedelta(days=5), []).today is None


def test_countdown_wording() -> None:
    assert countdown_text("Quiz", 9) == "Quiz is in 9 days."
    assert countdown_text("Quiz", 1) == "Quiz is tomorrow."
    assert countdown_text("Quiz", 0) == "Quiz is today."
    assert countdown_text("Quiz", -1) == "Quiz was 1 day ago."
    assert countdown_text("Quiz", -4) == "Quiz was 4 days ago."


def test_the_reason_gives_the_chapters_score_or_says_it_has_no_evidence() -> None:
    scored = weak(4)
    assert why_chapter("Quiz", 3, scored) == (
        "Quiz is in 3 days. Chapter 4 is at 20%: 2 of 10 words secure."
    )
    empty = chapter_readiness(ChapterEvidence(uuid.uuid4(), 2, "K2"), 85)
    assert why_chapter("Quiz", 3, empty) == (
        "Quiz is in 3 days. Chapter 2 has no evidence yet: add its words and answer review cards."
    )
