"""Measures how well the configured AI model corrects A1 German.

Run it after changing a model name or a prompt, before relying on the change:

    uv run python -m app.ai.evaluate               # the first provider that has a key
    uv run python -m app.ai.evaluate groq_backup   # a named one

It sends about 17 short requests to the real provider (roughly 12,000 tokens of the day's
allowance), paced to stay inside a free plan's per-minute limit, and scores each answer the way
the learner would see it: after the same filtering the sentence coach applies. No database, no
cache, and nothing the learner wrote: only the fixed sentences below.

What a good result looks like: every sentence with an error ends up as one of its accepted
corrections, and no correct sentence is "corrected". A model that fails the correct sentences
is worse for a beginner than one that misses an error: it teaches mistakes.
"""

import asyncio
import sys
from dataclasses import dataclass

import httpx

from app.ai.errors import ProviderError
from app.ai.prompts import (
    EXERCISE_HELP,
    SENTENCE_COACH,
    ExerciseHelpOut,
    SentenceCoachOut,
)
from app.ai.providers import AiProvider, build_providers
from app.coach import merge
from app.coach.merge import AiIssue
from app.coach.service import TOPICS, overall_explanation
from app.core.config import get_settings
from app.scanner import verify

PAUSE_SECONDS = 5.0  # about 12 requests a minute: inside Groq's free tokens-per-minute limit

# (what the learner wrote, the corrections we accept; None = the sentence is already correct)
COACH_CASES: list[tuple[str, set[str] | None]] = [
    ("Ich habe ein Tisch gekauft.", {"Ich habe einen Tisch gekauft."}),  # accusative
    ("Heute ich gehe ins Kino.", {"Heute gehe ich ins Kino."}),  # verb second
    ("Am Montag ich habe Deutschkurs.", {"Am Montag habe ich Deutschkurs."}),  # verb second
    ("Wo du wohnst?", {"Wo wohnst du?"}),  # question word order
    ("Ich habe nicht Auto.", {"Ich habe kein Auto."}),  # kein / nicht
    ("Ich fahre mit der Bus zur Arbeit.", {"Ich fahre mit dem Bus zur Arbeit."}),  # dative
    ("Das Mädchen spielt mit ihre Puppe.", {"Das Mädchen spielt mit ihrer Puppe."}),  # dative
    ("Ich muss gehen jetzt nach Hause.", {"Ich muss jetzt nach Hause gehen."}),  # modal verb
    ("Ich aufstehe um 6 Uhr.", {"Ich stehe um 6 Uhr auf."}),  # separable verb
    ("Meine Schwester haben zwei Kinder.", {"Meine Schwester hat zwei Kinder."}),  # verb ending
    ("Ich bin gestern nach Berlin gefahrt.", {"Ich bin gestern nach Berlin gefahren."}),  # Perfekt
    ("Er kann gut Deutsch sprechen.", None),
    ("Ich stehe jeden Tag um 7 Uhr auf.", None),
    ("Wir sind gestern ins Kino gegangen.", None),
    ("Ich wohne in Berlin und ich bin 20 Jahre alt.", None),
    ("Ich möchte einen Kaffee, bitte.", None),
]

EXERCISE = (
    "Ergänzen Sie die Verben.\n1 Ich ___ aus Pakistan. (kommen)\n2 Wo ___ du? (wohnen)\n"
    "3 Er ___ Deutsch und Englisch. (sprechen)\n4 Wir ___ in Berlin. (sein)\n"
    "5 ___ ihr müde? (sein)"
)
EXERCISE_ANSWERS = ["komme", "wohnst", "spricht", "sind", "seid"]


@dataclass(frozen=True)
class CoachScore:
    passed: bool
    shown: str | None  # the text the learner would be offered, or None if left as written
    contradiction: bool  # "No errors found." written next to a correction


def score_coach(text: str, accepted: set[str] | None, output: SentenceCoachOut) -> CoachScore:
    """Scores one answer as the learner would see it: after the coach's own filtering."""
    findings = merge.merge(text, [], [AiIssue(**i.model_dump()) for i in output.issues])
    shown = merge.apply_fixes(text, findings)
    contradiction = bool(findings) and overall_explanation(output.explanation, findings) is None
    if accepted is None:
        return CoachScore(not findings, shown, contradiction)
    return CoachScore(shown in accepted, shown, contradiction)


@dataclass(frozen=True)
class ExerciseScore:
    right: int
    total: int
    misfits: int  # answers that don't fit the printed line (would be shown as Uncertain)
    leaked_hints: int  # hints that contain the answer (would be replaced)


def score_exercise(output: ExerciseHelpOut, answers: list[str]) -> ExerciseScore:
    given = [i.answer.strip().lower() for i in output.items]
    right = sum(1 for want, got in zip(answers, given, strict=False) if want == got)
    misfits = sum(
        1
        for i in output.items
        if i.filled
        and not (
            verify.answer_in_sentence(i.answer, i.filled)
            and verify.sentence_matches_task(i.task, i.filled) is not False
        )
    )
    leaked = sum(1 for i in output.items if verify.hint_gives_answer(i.hint, i.answer))
    return ExerciseScore(right, len(answers), misfits, leaked)


async def run(provider: AiProvider) -> bool:
    """Prints a report. True if the model is good enough to rely on."""
    print(f"Provider: {provider.name}, model: {provider.model}\n")
    passed = false_corrections = contradictions = failed_calls = 0

    for text, accepted in COACH_CASES:
        request = SENTENCE_COACH.render({"sentence": text, "findings": "none", "topics": TOPICS})
        try:
            response = await provider.generate(request)
            output = SentenceCoachOut.model_validate(response.data)
        except (ProviderError, ValueError) as exc:
            failed_calls += 1
            print(f"  FAILED CALL  {text}\n               {type(exc).__name__}: {exc}")
            await asyncio.sleep(PAUSE_SECONDS)
            continue
        score = score_coach(text, accepted, output)
        passed += score.passed
        contradictions += score.contradiction
        if accepted is None and not score.passed:
            false_corrections += 1
        mark = "ok  " if score.passed else "MISS"
        print(f"  {mark} {text}")
        if not score.passed:
            want = "left alone" if accepted is None else " / ".join(sorted(accepted))
            print(f"         wanted: {want}\n         shown:  {score.shown or '(left alone)'}")
        if score.contradiction:
            print('         says "No errors found." next to a correction')
        await asyncio.sleep(PAUSE_SECONDS)

    exercise: ExerciseScore | None = None
    try:
        response = await provider.generate(
            EXERCISE_HELP.render({"exercise": EXERCISE, "topics": TOPICS})
        )
        exercise = score_exercise(ExerciseHelpOut.model_validate(response.data), EXERCISE_ANSWERS)
    except (ProviderError, ValueError) as exc:
        failed_calls += 1
        print(f"  FAILED CALL  exercise: {type(exc).__name__}: {exc}")

    total = len(COACH_CASES)
    print(f"\nSentence coach: {passed} of {total} right")
    print(f"  correct sentences wrongly 'corrected': {false_corrections}")
    print(f"  'No errors found.' beside a correction: {contradictions} (hidden by the coach)")
    if exercise:
        print(
            f"Exercise answers: {exercise.right} of {exercise.total} right, "
            f"{exercise.misfits} not fitting the printed line, "
            f"{exercise.leaked_hints} hints giving the answer away"
        )
    print(f"Calls that failed or gave unusable output: {failed_calls}")

    good = (
        passed >= total - 1
        and false_corrections == 0
        and failed_calls == 0
        and exercise is not None
        and exercise.right >= exercise.total - 1
    )
    print("\nVerdict:", "good enough to rely on." if good else "NOT good enough: see above.")
    return good


async def main(name: str | None) -> int:
    async with httpx.AsyncClient() as http:
        providers = build_providers(get_settings(), http)
        if name:
            providers = [p for p in providers if p.name == name]
        if not providers:
            print(
                "No AI provider with a key is configured" + (f" under '{name}'." if name else ".")
            )
            return 2
        return 0 if await run(providers[0]) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None)))
