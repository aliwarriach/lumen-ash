"""Combines what LanguageTool, our rules and the AI each found into one list of corrections,
and decides how much to trust each.

    Confirmed   LanguageTool flagged it AND our rules agree with the fix (see rules.py).
    Likely      One source flagged it (the AI, or LanguageTool when it is reasonably sure), or
                LanguageTool and the AI agree on the same fix.
    Uncertain   LanguageTool and the AI disagree about the fix, or LanguageTool flagged it but
                says itself it is unsure. Shown with "verify with your teacher".

The AI only ever adds "Likely" findings or agrees with another source. It can never turn a
finding into "Confirmed". A correction of the AI's own is sent back through LanguageTool with the
fix applied (see service.recheck_ai_fixes): if LanguageTool objects to the corrected words, the
correction drops to "Uncertain".
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey

# LanguageTool's own confidence below this, with nothing else to back it up, is "Uncertain".
LT_CONFIDENCE_FLOOR = 0.5


class Label(StrEnum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCERTAIN = "uncertain"


class Source(StrEnum):
    LANGUAGETOOL = "languagetool"
    RULES = "rules"
    AI = "ai"


@dataclass(frozen=True)
class LtFinding:
    """A LanguageTool match, already mapped to a pattern and checked by our rules."""

    start: int
    end: int
    wrong: str
    correct: str
    pattern_key: PatternKey | None
    category: MistakeCategory
    verified_reason: str | None  # set when our rules agree with `correct`
    message: str
    confidence: float | None
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class AiIssue:
    """An error the AI says it found, with the exact wrong text copied from the sentence."""

    wrong: str
    correct: str
    topic: str | None = None
    why: str | None = None


@dataclass
class Finding:
    start: int
    end: int
    wrong: str
    correct: str
    label: Label
    sources: list[Source]
    pattern_key: PatternKey | None
    category: MistakeCategory
    explanation: str | None
    alternatives: list[str] = field(default_factory=list)


def same_text(a: str, b: str) -> bool:
    """Same words, ignoring spacing. Case matters: in German 'ich' and 'Ich' are different."""
    return " ".join(a.split()) == " ".join(b.split())


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def locate(text: str, wrong: str) -> tuple[int, int] | None:
    """Where the AI's `wrong` text is in the sentence. None if it isn't there exactly once:
    an error the AI can't point to is not shown."""
    wrong = wrong.strip()
    if not wrong:
        return None
    first = text.find(wrong)
    if first == -1 or text.find(wrong, first + 1) != -1:
        return None
    return first, first + len(wrong)


def usable_fix(correct: str) -> bool:
    """Whether the AI's replacement can be put into the sentence as it stands.

    Models sometimes answer a word-order error with "stehe ... auf", or with nothing at all.
    Applied literally that would give the learner "Ich stehe ... auf um 6 Uhr."."""
    text = correct.strip()
    return bool(text) and "..." not in text and "…" not in text and "[" not in text


def _topic(topic: str | None) -> PatternKey | None:
    try:
        return PatternKey(topic) if topic else None
    except ValueError:
        return None


def merge(text: str, lt: list[LtFinding], ai: list[AiIssue]) -> list[Finding]:
    located: list[tuple[int, int, AiIssue]] = []
    for issue in ai:
        span = locate(text, issue.wrong)
        if span is None or same_text(issue.wrong, issue.correct) or not usable_fix(issue.correct):
            continue
        if any(_overlaps(*span, s, e) for s, e, _ in located):
            continue  # the AI repeated itself
        located.append((*span, issue))
    unused = list(located)

    findings: list[Finding] = []
    for f in lt:
        partner = next(((s, e, i) for s, e, i in unused if _overlaps(f.start, f.end, s, e)), None)
        if partner is not None:
            unused.remove(partner)
        sources = [Source.LANGUAGETOOL]
        alternatives = list(f.alternatives)
        explanation = f.verified_reason
        agree = partner is not None and same_text(partner[2].correct, f.correct)

        if f.verified_reason is not None:
            label = Label.CONFIRMED
            sources.append(Source.RULES)
            if agree:
                sources.append(Source.AI)
        elif partner is not None and agree:
            label = Label.LIKELY
            sources.append(Source.AI)
            explanation = partner[2].why
        elif partner is not None:
            label = Label.UNCERTAIN
            alternatives.insert(0, partner[2].correct)
            explanation = partner[2].why
        elif f.confidence is not None and f.confidence < LT_CONFIDENCE_FLOOR:
            label = Label.UNCERTAIN
        else:
            label = Label.LIKELY
        if explanation is None and f.pattern_key is None and f.category != MistakeCategory.SPELLING:
            explanation = f.message or None  # German, but better than nothing
        findings.append(
            Finding(
                f.start,
                f.end,
                f.wrong,
                f.correct,
                label,
                sources,
                f.pattern_key,
                f.category,
                explanation,
                [a for a in dict.fromkeys(alternatives) if not same_text(a, f.correct)],
            )
        )

    for start, end, issue in unused:
        pattern = _topic(issue.topic)
        findings.append(
            Finding(
                start,
                end,
                text[start:end],
                issue.correct.strip(),
                Label.LIKELY,
                [Source.AI],
                pattern,
                PATTERNS[pattern].category if pattern else MistakeCategory.OTHER,
                issue.why,
            )
        )
    return sorted(findings, key=lambda f: (f.start, f.end))


# --- Sentences ---

_SENTENCE_END = re.compile(r"[.!?\n]")


def sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """The start and end of the sentence (or line) that contains the span."""
    before = max((m.end() for m in _SENTENCE_END.finditer(text, 0, start)), default=0)
    after = _SENTENCE_END.search(text, end)
    return before, after.end() if after else len(text)


def corrected_sentence(text: str, finding: Finding) -> tuple[str, int, int]:
    """The sentence with this one correction applied, and where the new words are in it."""
    s, e = sentence_bounds(text, finding.start, finding.end)
    raw = text[s : finding.start] + finding.correct + text[finding.end : e]
    lead = len(raw) - len(raw.lstrip())
    start = finding.start - s - lead
    return raw.strip(), start, start + len(finding.correct)


def sentence_with_fix(text: str, finding: Finding) -> tuple[str, str]:
    """The sentence containing the error as written, and the same sentence corrected."""
    s, e = sentence_bounds(text, finding.start, finding.end)
    return text[s:e].strip(), corrected_sentence(text, finding)[0]


def count_sentences(text: str) -> int:
    return len([p for p in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if p.strip()])


def apply_fixes(text: str, findings: list[Finding]) -> str | None:
    """The text with every Confirmed and Likely correction applied, or None if there are none.
    Uncertain corrections are left as written. If two overlap, the more trusted one wins."""
    rank = {Label.CONFIRMED: 0, Label.LIKELY: 1}
    chosen: list[Finding] = []
    for f in sorted(
        (f for f in findings if f.label in rank), key=lambda f: (rank[f.label], f.start)
    ):
        if not any(_overlaps(f.start, f.end, c.start, c.end) for c in chosen):
            chosen.append(f)
    if not chosen:
        return None
    out = text
    for f in sorted(chosen, key=lambda f: f.start, reverse=True):
        out = out[: f.start] + f.correct + out[f.end :]
    return out
