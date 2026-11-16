"""Test readiness, worked out from the learner's own evidence. Pure functions.

Every number must be explainable in one sentence. The rules:

Per chapter, three parts, each only counted when there is evidence for it:
    vocabulary  share of the chapter's words that are Usable or Mastered   (weight 40)
    grammar     accuracy on the patterns linked to the chapter, last 30 days (weight 40)
    workbook    share of the chapter's workbook exercises marked done        (weight 20)
The chapter score is the weighted average of the parts that have evidence. A chapter with no
evidence at all counts as 0 in the overall number and is listed as a gap: not studied is not
the same as ready.

Overall: the mean of the chapter scores, blended 50/50 with the average of the learner's
recent practice tests when there are some. It is compared with the learner's own goal.

This is a rough estimate, not a prediction of the test mark, and it says so.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

WEIGHTS = {"vocabulary": 40, "grammar": 40, "workbook": 20}
MIN_GRAMMAR_ATTEMPTS = 3
NEAR_MARGIN = 10  # within this many points of the goal is "almost"
RECENT_CHAPTERS = 3
MAX_FOCUS = 4


class Verdict(StrEnum):
    READY = "ready"
    ALMOST = "almost"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ChapterEvidence:
    id: UUID
    number: int
    title: str
    words_total: int = 0
    words_secure: int = 0
    unsecure_words: list[str] = field(default_factory=list)  # weakest first
    patterns_linked: int = 0
    grammar_attempts: int = 0
    grammar_correct: int = 0
    weak_patterns: list[str] = field(default_factory=list)
    workbook_total: int = 0
    workbook_done: int = 0
    lost_marks_in: list[str] = field(default_factory=list)  # e.g. "practice test on 2 Nov"


@dataclass(frozen=True)
class Part:
    name: str
    score: float | None
    detail: str


@dataclass(frozen=True)
class ChapterReadiness:
    id: UUID
    number: int
    title: str
    score: float | None
    parts: list[Part]
    detail: str
    needs_work: bool
    unsecure_words: list[str]
    weak_patterns: list[str]
    lost_marks_in: list[str]


@dataclass(frozen=True)
class SkillReadiness:
    skill: str
    score: float | None
    detail: str
    tracked: bool  # False: the app has no evidence of its own, only test sections you entered


@dataclass(frozen=True)
class Readiness:
    verdict: Verdict
    target: int
    headline: str
    chapters: list[ChapterReadiness]
    chapters_total: int
    chapters_with_evidence: int
    skills: list[SkillReadiness]
    estimate: float | None = None
    learning_score: float | None = None
    practice_score: float | None = None
    recent_score: float | None = None
    scope_note: str | None = None
    reasons: list[str] = field(default_factory=list)
    focus: list[ChapterReadiness] = field(default_factory=list)  # to work on, in course order


def _pct(part: int, whole: int) -> float:
    return 100.0 * part / whole


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def chapter_readiness(e: ChapterEvidence, target: int) -> ChapterReadiness:
    parts: list[Part] = []

    if e.words_total:
        parts.append(
            Part(
                "vocabulary",
                _pct(e.words_secure, e.words_total),
                f"{e.words_secure} of {_plural(e.words_total, 'word')} secure",
            )
        )
    else:
        parts.append(Part("vocabulary", None, "No words added for this chapter yet."))

    if e.grammar_attempts >= MIN_GRAMMAR_ATTEMPTS:
        wrong = e.grammar_attempts - e.grammar_correct
        parts.append(
            Part(
                "grammar",
                _pct(e.grammar_correct, e.grammar_attempts),
                f"{wrong} wrong out of {_plural(e.grammar_attempts, 'checked answer')}",
            )
        )
    elif e.patterns_linked:
        parts.append(Part("grammar", None, "Not enough checked answers about its grammar yet."))
    else:
        parts.append(Part("grammar", None, "No grammar patterns linked to this chapter."))

    if e.workbook_total:
        done = f"{e.workbook_done} of {_plural(e.workbook_total, 'workbook exercise')} done"
        parts.append(Part("workbook", _pct(e.workbook_done, e.workbook_total), done))
    else:
        parts.append(Part("workbook", None, "No workbook exercises added."))

    weighted = [(WEIGHTS[p.name], p.score) for p in parts if p.score is not None]
    total_weight = sum(w for w, _ in weighted)
    score = sum(w * v for w, v in weighted) / total_weight if weighted else None
    if score is None:
        detail = "No evidence yet. Add this chapter's words and answer review cards."
    else:
        detail = "; ".join(p.detail for p in parts if p.score is not None)
    return ChapterReadiness(
        id=e.id,
        number=e.number,
        title=e.title,
        score=score,
        parts=parts,
        detail=detail,
        needs_work=score is None or score < target,
        unsecure_words=e.unsecure_words,
        weak_patterns=e.weak_patterns,
        lost_marks_in=e.lost_marks_in,
    )


def format_chapters(numbers: list[int]) -> str:
    """[4, 5, 6] -> 'Chapters 4–6'; [5] -> 'Chapter 5'; [2, 4, 5, 6] -> 'Chapters 2 and 4–6'."""
    nums = sorted(set(numbers))
    runs: list[list[int]] = []
    for n in nums:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    labels: list[str] = []
    for run in runs:
        if len(run) >= 3:
            labels.append(f"{run[0]}–{run[-1]}")
        else:
            labels += [str(n) for n in run]
    joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + f" and {labels[-1]}"
    return f"{'Chapter' if len(nums) == 1 else 'Chapters'} {joined}"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _skills(
    evidence: list[ChapterEvidence], test_skill_scores: dict[str, float]
) -> list[SkillReadiness]:
    words = sum(e.words_total for e in evidence)
    secure = sum(e.words_secure for e in evidence)
    attempts = sum(e.grammar_attempts for e in evidence)
    correct = sum(e.grammar_correct for e in evidence)
    out = [
        SkillReadiness(
            "vocabulary",
            _pct(secure, words) if words else None,
            f"{secure} of {_plural(words, 'word')} secure across these chapters"
            if words
            else "No words added for these chapters yet.",
            tracked=True,
        ),
        SkillReadiness(
            "grammar",
            _pct(correct, attempts) if attempts >= MIN_GRAMMAR_ATTEMPTS else None,
            f"{attempts - correct} wrong out of {_plural(attempts, 'checked answer')}, last 30 days"
            if attempts >= MIN_GRAMMAR_ATTEMPTS
            else "Not enough checked answers yet.",
            tracked=True,
        ),
    ]
    for skill in ("reading", "listening", "writing", "speaking"):
        score = test_skill_scores.get(skill)
        out.append(
            SkillReadiness(
                skill,
                score,
                "From the section scores of your recent practice tests."
                if score is not None
                else "Not tracked in the app. Enter section scores with a practice test.",
                tracked=False,
            )
        )
    return out


def assess(
    evidence: list[ChapterEvidence],
    practice_percents: list[float],
    target: int,
    test_skill_scores: dict[str, float] | None = None,
) -> Readiness:
    chapters = [chapter_readiness(e, target) for e in sorted(evidence, key=lambda e: e.number)]
    with_data = [c for c in chapters if c.score is not None]
    skills = _skills(evidence, test_skill_scores or {})

    def result(verdict: Verdict, headline: str, **more: Any) -> Readiness:
        return Readiness(
            verdict, target, headline, chapters, len(chapters), len(with_data), skills, **more
        )

    if not chapters:
        return result(
            Verdict.UNKNOWN,
            "Add the chapters this test covers, then the app can judge your readiness.",
        )

    learning = _mean([c.score or 0.0 for c in chapters]) if with_data else None
    practice = _mean(practice_percents)

    needing = [c for c in chapters if c.needs_work]
    weakest = sorted(needing, key=lambda c: (-1.0 if c.score is None else c.score, c.number))
    focus = sorted(weakest[:MAX_FOCUS], key=lambda c: c.number)
    focus_text = format_chapters([c.number for c in focus]) if focus else None

    if learning is None and practice is None:
        # No verdict, but the chapters with nothing in them are still the place to start.
        return result(
            Verdict.UNKNOWN,
            "Not enough information yet. Add words and answer review cards so the app can "
            "judge your readiness.",
            focus=focus,
        )

    if learning is None:
        estimate = practice
    elif practice is None:
        estimate = learning
    else:
        estimate = (learning + practice) / 2
    assert estimate is not None
    recent = _mean([c.score for c in with_data[-RECENT_CHAPTERS:] if c.score is not None])

    if estimate >= target:
        verdict = Verdict.READY
        headline = f"Looking ready: about {round(estimate)}% against your {target}% goal."
        if focus_text:
            headline += f" Still weak: {focus_text}."
    elif estimate >= target - NEAR_MARGIN:
        verdict = Verdict.ALMOST
        headline = f"Almost ready: about {round(estimate)}% against your {target}% goal."
        if focus_text:
            headline += f" Focus on {focus_text}."
    else:
        verdict = Verdict.NOT_READY
        headline = (
            f"Not ready yet: focus on {focus_text}."
            if focus_text
            else "Not ready yet: your recent practice tests are below your goal."
        )

    reasons = []
    for c in focus:
        reasons.append(
            f"Chapter {c.number} ({c.title}): "
            + (f"{round(c.score)}%. {c.detail}." if c.score is not None else c.detail)
        )
    if practice is not None:
        reasons.append(
            f"Practice tests: {round(practice)}% on average over your last "
            f"{_plural(len(practice_percents), 'result')}."
        )

    scope_note = None
    if recent is not None and learning is not None and recent >= target > learning:
        scope_note = "Ready for your most recent chapters, but not yet for the whole syllabus."

    return result(
        verdict,
        headline,
        estimate=estimate,
        learning_score=learning,
        practice_score=practice,
        recent_score=recent,
        scope_note=scope_note,
        reasons=reasons,
        focus=focus,
    )
