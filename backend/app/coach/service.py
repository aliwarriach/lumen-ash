"""The sentence coach: check -> map and verify -> explain -> merge -> save.

Each source is optional. LanguageTool down: the AI still checks. AI over its limit or down:
LanguageTool and our rules still check, and the explanation and practice come from our own
grammar catalog. Both down: nothing is saved and the learner is told so, because "no mistakes
found" from a checker that didn't run would be false reassurance.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AiBadResponseError, AiError, AiLimitError, AiUnavailableError
from app.ai.gateway import AiGateway
from app.ai.prompts import SENTENCE_COACH, SentenceCoachOut
from app.ai.redact import redact
from app.coach import merge, rules
from app.coach.languagetool import LanguageToolClient, LanguageToolUnavailable, LtMatch
from app.coach.merge import AiIssue, Finding, Label, LtFinding, Source
from app.coach.models import (
    CoachCheck,
    CoachCorrection,
    CorrectionStatus,
    Decision,
    WritingTask,
)
from app.coach.rules import DictData, NounInfo, VerbInfo
from app.dictionary.models import DictionaryEntry
from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey
from app.mistakes.service import log_mistake
from app.vocabulary.models import VocabWord

log = logging.getLogger(__name__)

TOPICS = ", ".join(k.value for k in PatternKey)
MAX_LOOKUP_WORDS = 80
MISTAKE_SOURCE = "Sentence coach"


# --- Dictionary lookup for the rule checks ---


async def load_dictionary(session: AsyncSession, words: set[str]) -> DictData:
    if not words:
        return DictData()
    entries = await session.scalars(
        select(DictionaryEntry).where(
            DictionaryEntry.lemma_lower.in_(sorted(words)[:MAX_LOOKUP_WORDS]),
            DictionaryEntry.pos.in_(["noun", "verb"]),
        )
    )
    genders: dict[str, set[str]] = {}
    plurals: dict[str, set[str]] = {}
    lemmas: dict[str, str] = {}
    verbs: dict[str, VerbInfo] = {}
    for e in entries:
        if e.pos == "noun":
            genders.setdefault(e.lemma_lower, set()).update(e.genders)
            plurals.setdefault(e.lemma_lower, set()).update(e.plurals)
            lemmas.setdefault(e.lemma_lower, e.lemma)
        else:
            present = (e.verb_forms or {}).get("present") or {}
            if present and e.lemma_lower not in verbs:
                verbs[e.lemma_lower] = VerbInfo(e.lemma, {k: v for k, v in present.items() if v})
    nouns = {
        key: NounInfo(lemmas[key], frozenset(genders[key]), frozenset(plurals[key]))
        for key in genders
    }
    return DictData(nouns, verbs)


# --- LanguageTool matches -> findings ---


def _starts_sentence(text: str, start: int) -> bool:
    before = text[:start]
    return not before.strip() or before.rstrip(" ").endswith((".", "!", "?", "\n"))


def build_lt_findings(text: str, matches: Sequence[LtMatch], data: DictData) -> list[LtFinding]:
    findings: list[LtFinding] = []
    taken_until = -1
    for m in sorted(matches, key=lambda m: (m.start, m.end)):
        wrong = text[m.start : m.end]
        if m.start < taken_until or not wrong.strip() or "[" in wrong:
            continue  # overlaps an earlier match, or touches a removed personal detail
        pattern, category = rules.map_rule(m.rule_id, m.category)
        start_of_sentence = _starts_sentence(text, m.start)

        # LanguageTool's first suggestion isn't always right ("Er gehen" -> "Er gehe"), so take
        # the first one our rules can confirm. If none, offer its first suggestion unconfirmed.
        correct, reason = m.replacements[0], None
        for candidate in m.replacements:
            reason = rules.verify(pattern, wrong, candidate, data, sentence_start=start_of_sentence)
            if reason:
                correct = candidate
                break
        if merge.same_text(wrong, correct):
            continue
        findings.append(
            LtFinding(
                start=m.start,
                end=m.end,
                wrong=wrong,
                correct=correct,
                pattern_key=pattern,
                category=category,
                verified_reason=reason,
                message=m.message,
                confidence=m.confidence,
                alternatives=tuple(r for r in m.replacements if r != correct),
            )
        )
        taken_until = m.end
    return findings


# --- The check ---


@dataclass
class AiOutcome:
    status: str  # ok | cached | limit | unavailable | error
    message: str | None = None
    output: SentenceCoachOut | None = None


async def _ask_ai(
    gateway: AiGateway, user_id: UUID, text: str, lt: Sequence[LtFinding]
) -> AiOutcome:
    findings = (
        "; ".join(
            f"{f.wrong} -> {f.correct}" + (f" [{f.pattern_key.value}]" if f.pattern_key else "")
            for f in lt
        )[:300]
        or "none"
    )
    try:
        result = await gateway.run(
            user_id, SENTENCE_COACH, {"sentence": text, "findings": findings, "topics": TOPICS}
        )
    except AiLimitError as exc:
        return AiOutcome("limit", exc.message)
    except AiBadResponseError as exc:
        return AiOutcome("error", exc.message)
    except AiError as exc:  # unavailable, shared limit, input too long
        return AiOutcome("unavailable", exc.message)
    assert isinstance(result.output, SentenceCoachOut)
    return AiOutcome("cached" if result.cached else "ok", None, result.output)


# What the AI is told to write when the text has no error at all.
_NO_ERRORS = re.compile(
    r"^\W*no (?:errors?|mistakes?)(?: (?:were |was )?found)?\W*$", re.IGNORECASE
)


def overall_explanation(ai_text: str | None, findings: Sequence[Finding]) -> str | None:
    """The AI's summary, unless it says "No errors found." while corrections are shown.

    That happens when the AI describes only its own findings and LanguageTool found the error,
    or when it simply contradicts itself. Each correction carries its own explanation, so
    showing none is better than telling the learner there is nothing wrong."""
    text = (ai_text or "").strip()
    if not text or (findings and _NO_ERRORS.match(text)):
        return None
    return text


async def recheck_ai_fixes(
    languagetool: LanguageToolClient | None, text: str, findings: Sequence[Finding]
) -> None:
    """Sends each AI-only correction back through LanguageTool, applied to its sentence.

    Nothing else checks what the AI alone found. If LanguageTool objects to the words the AI
    wrote, the "correction" is itself doubtful and drops to Uncertain ("verify with your
    teacher"), which also keeps it out of the suggested text. One request for all of them. If
    LanguageTool can't answer, they stay Likely: unverified, as before."""
    ai_only = [f for f in findings if f.sources == [Source.AI]]
    if languagetool is None or not ai_only:
        return
    parts: list[str] = []
    spans: list[tuple[Finding, int, int]] = []
    position = 0
    for f in ai_only:
        sentence, start, end = merge.corrected_sentence(text, f)
        spans.append((f, position + start, position + end))
        parts.append(sentence)
        position += len(sentence) + 1
    try:
        objections = await languagetool.check("\n".join(parts))
    except LanguageToolUnavailable as exc:
        log.warning("LanguageTool unavailable for the re-check: %s", exc)
        return
    for m in objections:
        for f, start, end in spans:
            if m.start < end and start < m.end:
                f.label = Label.UNCERTAIN


def _explanation(f: Finding) -> str | None:
    if f.explanation:
        return f.explanation
    if f.pattern_key:
        return PATTERNS[f.pattern_key].explanation
    if f.category == MistakeCategory.SPELLING:
        return f"Possible spelling mistake: check how '{f.wrong}' is spelled."
    return None


async def run_check(
    session: AsyncSession,
    gateway: AiGateway,
    languagetool: LanguageToolClient | None,
    user_id: UUID,
    text: str,
    task: WritingTask | None,
    redact_names: Sequence[str] = (),
) -> tuple[CoachCheck, list[CoachCorrection]]:
    # Everything from here on, including what is saved, uses the text with personal details
    # removed: that is also all that LanguageTool and the AI ever see.
    clean = redact(text, redact_names)

    matches: list[LtMatch] | None = None
    if languagetool is not None:
        try:
            matches = await languagetool.check(clean)
        except LanguageToolUnavailable as exc:
            log.warning("LanguageTool unavailable: %s", exc)

    data = await load_dictionary(
        session,
        rules.words_to_look_up(
            *(clean[m.start : m.end] for m in matches or []),
            *(r for m in matches or [] for r in m.replacements),
        ),
    )
    lt_findings = build_lt_findings(clean, matches or [], data)

    ai = await _ask_ai(gateway, user_id, clean, lt_findings)
    checked_by: list[str] = []
    if matches is not None:
        checked_by.append("languagetool")
    if ai.output is not None:
        checked_by.append("ai")
    if not checked_by:
        if ai.status == "limit":
            raise AiLimitError("daily_limit", ai.message or "")
        raise AiUnavailableError(
            "Sentence checking isn't available right now. Please try again later."
        )

    findings = merge.merge(
        clean,
        lt_findings,
        [AiIssue(**i.model_dump()) for i in ai.output.issues] if ai.output else [],
    )
    await recheck_ai_fixes(languagetool if matches is not None else None, clean, findings)
    for f in findings:
        f.explanation = _explanation(f)

    practice = [p.strip() for p in ai.output.practice if p.strip()] if ai.output else []
    practice_source = "ai" if practice else None
    if not practice:
        patterns = [f.pattern_key for f in findings if f.pattern_key]
        if patterns:
            practice = [p.prompt for p in PATTERNS[patterns[0]].practice]
            practice_source = "catalog"

    check = CoachCheck(
        user_id=user_id,
        task_id=task.id if task else None,
        text=clean,
        redacted=clean != text,
        suggested_text=merge.apply_fixes(clean, findings),
        sentence_count=merge.count_sentences(clean),
        explanation=overall_explanation(ai.output.explanation if ai.output else None, findings),
        practice=practice,
        practice_source=practice_source,
        checked_by=checked_by,
        ai_status=ai.status,
        ai_message=ai.message,
    )
    session.add(check)
    await session.flush()

    corrections = []
    for f in findings:
        sentence_wrong, sentence_correct = merge.sentence_with_fix(clean, f)
        corrections.append(
            CoachCorrection(
                user_id=user_id,
                check_id=check.id,
                start=f.start,
                end=f.end,
                wrong=f.wrong,
                correct=f.correct,
                sentence_wrong=sentence_wrong,
                sentence_correct=sentence_correct,
                label=f.label,
                pattern_key=f.pattern_key,
                category=f.category,
                explanation=f.explanation,
                sources=[s.value for s in f.sources],
                alternatives=f.alternatives,
                status=CorrectionStatus.PENDING,
            )
        )
    session.add_all(corrections)
    await session.commit()
    return check, corrections


# --- Writing tasks ---


async def task_progress(
    session: AsyncSession, user_id: UUID, tasks: Sequence[WritingTask]
) -> dict[UUID, tuple[int, bool]]:
    """task id -> (number of checks, done)."""
    if not tasks:
        return {}
    rows = await session.execute(
        select(
            CoachCheck.task_id,
            func.count(),
            func.max(CoachCheck.sentence_count),
        )
        .where(CoachCheck.user_id == user_id, CoachCheck.task_id.in_([t.id for t in tasks]))
        .group_by(CoachCheck.task_id)
    )
    stats = {task_id: (count, best or 0) for task_id, count, best in rows}
    return {
        t.id: (stats.get(t.id, (0, 0))[0], stats.get(t.id, (0, 0))[1] >= t.min_sentences)
        for t in tasks
    }


# --- The learner's decision ---


class DecisionError(Exception):
    """The decision isn't allowed in the correction's current state."""


async def decide(
    session: AsyncSession, user_id: UUID, correction: CoachCorrection, decision: Decision
) -> CoachCorrection:
    """Accept (adds it to the mistake log), reject, or flag a correction.

    Repeating the same decision is harmless. A decided correction can't be flipped, except that
    a flagged one can still be accepted or rejected once the learner has asked the teacher.
    """
    target = {
        Decision.ACCEPT: CorrectionStatus.ACCEPTED,
        Decision.REJECT: CorrectionStatus.REJECTED,
        Decision.FLAG: CorrectionStatus.FLAGGED,
    }[decision]
    current = correction.status
    if current == target:
        return correction
    if current not in (CorrectionStatus.PENDING, CorrectionStatus.FLAGGED):
        raise DecisionError(f"This correction was already {current.value}.")

    if target == CorrectionStatus.ACCEPTED:
        words = await _owned_words_in(session, user_id, correction.sentence_wrong)
        mistake = await log_mistake(
            session,
            user_id,
            wrong=correction.sentence_wrong,
            correct=correction.sentence_correct,
            category=correction.category,
            pattern_key=correction.pattern_key,
            explanation=correction.explanation,
            source=MISTAKE_SOURCE,
            words=words,
        )
        correction.mistake_id = mistake.id
    correction.status = target
    await session.commit()
    return correction


async def _owned_words_in(session: AsyncSession, user_id: UUID, sentence: str) -> list[VocabWord]:
    """The learner's saved words that appear in the sentence, for the mistake's related words."""
    found = rules.words_to_look_up(sentence)
    if not found:
        return []
    words = await session.scalars(
        select(VocabWord)
        .where(VocabWord.user_id == user_id, func.lower(VocabWord.german).in_(sorted(found)))
        .limit(20)
    )
    return list(words)
