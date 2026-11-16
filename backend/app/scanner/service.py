"""Help with one textbook exercise that was photographed.

The photo is read on the phone, so what arrives here is plain text the learner has already looked
over. Nothing is stored: not the photo, not the text, not the answers. The AI call is cached and
counted like any other (see app/ai).

The AI's answers are not taken on trust. Each filled-in German sentence goes to LanguageTool, and
our dictionary checks verb endings (see verify.py):

    Confirmed   our dictionary proves the verb ending AND LanguageTool found nothing wrong.
    Likely      the AI's answer, and LanguageTool found nothing wrong or was not available.
    Uncertain   LanguageTool disagrees with the sentence, the AI itself says it is unsure, or
                the answer doesn't fit the exercise: it is not in the filled-in sentence, or that
                sentence is not the printed line with its gap filled.

As in the sentence coach, the AI alone can never make an answer "Confirmed". A hint that contains
the answer is replaced: the learner asked for a hint first, not the answer.
"""

import logging
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AiGateway
from app.ai.prompts import EXERCISE_HELP, ExerciseHelpOut, ExerciseItem
from app.coach.languagetool import LanguageToolClient, LanguageToolUnavailable
from app.coach.merge import Label
from app.coach.service import TOPICS, load_dictionary
from app.grammar.catalog import PATTERNS, PatternKey
from app.scanner import verify
from app.scanner.schemas import VERIFY_WARNING, ScanHelpOut, ScanItemOut

log = logging.getLogger(__name__)

NOTHING_USABLE = (
    "I could not work out any item from this text. Check that the text is complete, or "
    "ask your teacher."
)
_JOIN = "\n"


@dataclass
class _Looked:
    problems: list[str]  # what LanguageTool objected to, per item


async def _languagetool(
    languagetool: LanguageToolClient | None, items: list[ExerciseItem]
) -> dict[int, list[str]] | None:
    """The problems LanguageTool sees in each item's filled sentence, in one request.

    None means it did not run (not configured, down or over its own limit)."""
    if languagetool is None:
        return None
    spans: list[tuple[int, int, int]] = []  # item index, start, end in the joined text
    parts: list[str] = []
    position = 0
    for index, item in enumerate(items):
        if item.filled:
            spans.append((index, position, position + len(item.filled)))
            parts.append(item.filled)
            position += len(item.filled) + len(_JOIN)
    if not parts:
        return {}
    try:
        matches = await languagetool.check(_JOIN.join(parts))
    except LanguageToolUnavailable as exc:
        log.warning("LanguageTool unavailable for an exercise: %s", exc)
        return None
    problems: dict[int, list[str]] = {}
    for m in matches:
        for index, start, end in spans:
            if start <= m.start < end:
                problems.setdefault(index, []).append(m.message)
                break
    return problems


GENERIC_HINT = "Look at who or what the sentence is about, then at the word that is missing."


def _hint(item: ExerciseItem, pattern: PatternKey | None) -> str:
    if item.hint.strip() and not verify.hint_gives_answer(item.hint, item.answer):
        return item.hint
    return f"This is about: {PATTERNS[pattern].title}." if pattern else GENERIC_HINT


def _fits_exercise(item: ExerciseItem) -> bool:
    """The answer is in the filled-in sentence, and that sentence is the printed line."""
    if not item.filled:
        return True  # nothing to compare: the answer is not a German sentence
    return (
        verify.answer_in_sentence(item.answer, item.filled)
        and verify.sentence_matches_task(item.task, item.filled) is not False
    )


def _topic(key: str | None) -> PatternKey | None:
    try:
        return PatternKey(key) if key else None
    except ValueError:
        return None


async def help_with_exercise(
    session: AsyncSession,
    gateway: AiGateway,
    languagetool: LanguageToolClient | None,
    user_id: UUID,
    text: str,
) -> ScanHelpOut:
    result = await gateway.run(user_id, EXERCISE_HELP, {"exercise": text, "topics": TOPICS})
    output = cast(ExerciseHelpOut, result.output)
    # An item with no answer is of no use. (The model can leave one empty when it is unsure.)
    items = [i for i in output.items if i.answer.strip() and i.task.strip()]

    problems = await _languagetool(languagetool, items)
    data = await load_dictionary(
        session, {c for i in items if i.filled for c in verify.candidate_lemmas(i.filled)}
    )

    out: list[ScanItemOut] = []
    for index, item in enumerate(items):
        flagged = problems is not None and bool(problems.get(index))
        proof = verify.confirm_verb_ending(item.answer, item.filled, data) if item.filled else None
        label = Label.LIKELY
        if flagged or item.unsure or not _fits_exercise(item):
            label = Label.UNCERTAIN
        elif proof and problems is not None:
            label = Label.CONFIRMED
        pattern = _topic(item.topic)
        out.append(
            ScanItemOut(
                number=item.number,
                task=item.task,
                hint=_hint(item, pattern),
                answer=item.answer,
                filled=item.filled,
                label=label,
                warning=VERIFY_WARNING if label == Label.UNCERTAIN else None,
                verified_by=proof if label == Label.CONFIRMED else None,
                why=item.why or (PATTERNS[pattern].explanation if pattern else None),
                pattern_key=pattern,
                pattern_title=PATTERNS[pattern].title if pattern else None,
            )
        )

    limits = output.limits
    if not out and not limits:
        limits = NOTHING_USABLE
    return ScanHelpOut(
        instruction=output.instruction,
        items=out,
        limits=limits,
        checked_by=["ai", "languagetool"] if problems is not None else ["ai"],
        cached=result.cached,
    )
