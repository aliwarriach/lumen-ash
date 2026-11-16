import uuid

from app.exams.readiness import (
    MAX_FOCUS,
    ChapterEvidence,
    Verdict,
    assess,
    chapter_readiness,
    format_chapters,
)


def chapter(number: int, score: float | None = None, **kw: object) -> ChapterEvidence:
    """A chapter whose score comes out as `score` (from words alone), or no evidence if None."""
    if score is not None and "words_total" not in kw:
        kw = {"words_total": 100, "words_secure": round(score), **kw}
    return ChapterEvidence(uuid.uuid4(), number, f"Kapitel {number}", **kw)  # type: ignore[arg-type]


# --- One chapter ------------------------------------------------------------------------------


def test_a_chapter_scores_vocabulary_grammar_and_workbook_with_weights_40_40_20() -> None:
    c = chapter_readiness(
        chapter(
            3,
            words_total=20,
            words_secure=4,  # 20%
            patterns_linked=2,
            grammar_attempts=5,
            grammar_correct=3,  # 60%
            workbook_total=2,
            workbook_done=1,  # 50%
        ),
        target=85,
    )
    assert c.score == (20 * 40 + 60 * 40 + 50 * 20) / 100 == 42
    assert c.needs_work is True
    assert (
        c.detail
        == "4 of 20 words secure; 2 wrong out of 5 checked answers; 1 of 2 workbook exercises done"
    )


def test_parts_without_evidence_are_left_out_instead_of_counting_as_zero() -> None:
    c = chapter_readiness(chapter(1, words_total=10, words_secure=9), target=85)
    assert c.score == 90  # only vocabulary has evidence
    parts = {p.name: p for p in c.parts}
    assert parts["grammar"].score is None
    assert parts["grammar"].detail == "No grammar patterns linked to this chapter."
    assert parts["workbook"].detail == "No workbook exercises added."
    assert c.needs_work is False


def test_grammar_needs_three_checked_answers_before_it_counts() -> None:
    thin = chapter_readiness(
        chapter(1, words_total=10, words_secure=10, patterns_linked=1, grammar_attempts=2),
        target=85,
    )
    parts = {p.name: p for p in thin.parts}
    assert parts["grammar"].score is None
    assert parts["grammar"].detail == "Not enough checked answers about its grammar yet."


def test_a_chapter_with_no_evidence_has_no_score_and_needs_work() -> None:
    c = chapter_readiness(chapter(2), target=85)
    assert c.score is None and c.needs_work is True
    assert c.detail == "No evidence yet. Add this chapter's words and answer review cards."


# --- Wording ---------------------------------------------------------------------------------


def test_chapter_numbers_are_written_the_way_a_person_would() -> None:
    assert format_chapters([5]) == "Chapter 5"
    assert format_chapters([4, 5, 6]) == "Chapters 4–6"
    assert format_chapters([4, 5]) == "Chapters 4 and 5"
    assert format_chapters([2, 4, 6]) == "Chapters 2, 4 and 6"
    assert format_chapters([2, 4, 5, 6]) == "Chapters 2 and 4–6"
    assert format_chapters([6, 4, 5, 4]) == "Chapters 4–6"


# --- The verdict ---------------------------------------------------------------------------------


def test_not_ready_yet_focus_on_chapters_4_to_6() -> None:
    evidence = [chapter(n, 90) for n in (1, 2, 3)] + [chapter(n, 30) for n in (4, 5, 6)]
    r = assess(evidence, [], target=85)

    assert r.verdict == Verdict.NOT_READY
    assert r.headline == "Not ready yet: focus on Chapters 4–6."
    assert [c.number for c in r.focus] == [4, 5, 6]
    assert r.estimate == r.learning_score == 60
    assert r.reasons[0] == "Chapter 4 (Kapitel 4): 30%. 30 of 100 words secure."  # and says why


def test_ready_when_the_estimate_reaches_the_goal() -> None:
    r = assess([chapter(n, 90) for n in range(1, 5)], [], target=85)
    assert r.verdict == Verdict.READY
    assert r.headline == "Looking ready: about 90% against your 85% goal."
    assert r.focus == [] and r.reasons == []


def test_ready_overall_but_one_weak_chapter_is_still_named() -> None:
    evidence = [chapter(n, 95) for n in range(1, 8)] + [chapter(8, 60)]
    r = assess(evidence, [], target=85)
    assert r.verdict == Verdict.READY  # (7 * 95 + 60) / 8 is about 91
    assert r.headline == "Looking ready: about 91% against your 85% goal. Still weak: Chapter 8."


def test_within_ten_points_of_the_goal_is_almost() -> None:
    r = assess([chapter(1, 90), chapter(2, 70)], [], target=85)  # mean 80
    assert r.verdict == Verdict.ALMOST
    assert r.headline == "Almost ready: about 80% against your 85% goal. Focus on Chapter 2."


def test_a_chapter_with_no_evidence_counts_as_zero_and_is_the_first_gap() -> None:
    r = assess([chapter(1, 90), chapter(2)], [], target=85)
    assert r.learning_score == 45 and r.verdict == Verdict.NOT_READY
    assert r.headline == "Not ready yet: focus on Chapter 2."
    assert (
        r.reasons[0]
        == "Chapter 2 (Kapitel 2): No evidence yet. Add this chapter's words and answer review "
        "cards."
    )
    assert (r.chapters_with_evidence, r.chapters_total) == (1, 2)


def test_practice_tests_count_for_half() -> None:
    r = assess([chapter(1, 80)], [60.0, 60.0], target=85)
    assert r.estimate == 70 and r.practice_score == 60 and r.learning_score == 80
    assert r.verdict == Verdict.NOT_READY
    assert "Practice tests: 60% on average over your last 2 results." in r.reasons
    # Good practice results lift an otherwise weak picture, but only halfway.
    assert assess([chapter(1, 50)], [100.0], target=85).estimate == 75


def test_practice_tests_alone_are_enough_to_judge() -> None:
    r = assess([chapter(1)], [90.0], target=85)
    assert r.verdict == Verdict.READY and r.estimate == 90
    low = assess([chapter(1, 95)], [40.0], target=85)  # chapters fine, tests poor
    assert low.verdict == Verdict.NOT_READY and low.focus == []
    assert low.headline == "Not ready yet: your recent practice tests are below your goal."


def test_without_chapters_or_evidence_it_says_what_is_missing_instead_of_guessing() -> None:
    none = assess([], [], target=85)
    assert none.verdict == Verdict.UNKNOWN and none.estimate is None
    assert (
        none.headline == "Add the chapters this test covers, then the app can judge your readiness."
    )
    empty = assess([chapter(1), chapter(2)], [], target=85)
    assert empty.verdict == Verdict.UNKNOWN and empty.estimate is None
    assert empty.headline.startswith("Not enough information yet.")
    assert [c.number for c in empty.focus] == [1, 2]  # nothing to judge, but where to start


def test_recent_chapters_can_be_ready_while_the_whole_syllabus_is_not() -> None:
    evidence = [chapter(n, 40) for n in range(1, 6)] + [chapter(n, 95) for n in (6, 7, 8)]
    r = assess(evidence, [], target=85)
    assert r.recent_score == 95 and r.learning_score is not None and r.learning_score < 85
    assert (
        r.scope_note == "Ready for your most recent chapters, but not yet for the whole syllabus."
    )
    assert assess([chapter(n, 95) for n in range(1, 4)], [], target=85).scope_note is None


def test_at_most_four_chapters_are_named_and_they_are_the_weakest() -> None:
    evidence = [chapter(n, 10 * n) for n in range(1, 9)]  # chapter 1 is weakest
    r = assess(evidence, [], target=85)
    assert len(r.focus) == MAX_FOCUS
    assert [c.number for c in r.focus] == [1, 2, 3, 4]
    assert r.headline == "Not ready yet: focus on Chapters 1–4."


def test_the_goal_is_the_learners_own() -> None:
    evidence = [chapter(1, 70)]
    assert assess(evidence, [], target=85).verdict == Verdict.NOT_READY
    assert assess(evidence, [], target=60).verdict == Verdict.READY


# --- Skills ----------------------------------------------------------------------------------


def test_skills_pool_the_chapters_and_take_the_rest_from_test_sections() -> None:
    evidence = [
        chapter(1, words_total=10, words_secure=8, grammar_attempts=4, grammar_correct=3),
        chapter(2, words_total=10, words_secure=4, grammar_attempts=6, grammar_correct=3),
    ]
    r = assess(evidence, [], target=85, test_skill_scores={"listening": 72.0})
    skills = {s.skill: s for s in r.skills}
    assert skills["vocabulary"].score == 60 and skills["vocabulary"].tracked is True
    assert skills["vocabulary"].detail == "12 of 20 words secure across these chapters"
    assert skills["grammar"].score == 60
    assert skills["grammar"].detail == "4 wrong out of 10 checked answers, last 30 days"
    assert (skills["listening"].score, skills["listening"].tracked) == (72, False)
    assert skills["reading"].score is None
    assert skills["reading"].detail.startswith("Not tracked in the app.")
    assert [s.skill for s in r.skills] == [
        "vocabulary",
        "grammar",
        "reading",
        "listening",
        "writing",
        "speaking",
    ]
