"""The scoring behind `python -m app.ai.evaluate`, and the parsing of what a model may send."""

from typing import Any

from app.ai.evaluate import COACH_CASES, run, score_coach, score_exercise
from app.ai.prompts import ExerciseHelpOut, SentenceCoachOut
from app.ai.providers import AiRequest, AiResponse

SENTENCE = "Ich habe ein Tisch gekauft."
ACCEPTED = {"Ich habe einen Tisch gekauft."}


def coach(issues: list[dict[str, Any]], explanation: str = "Explained.") -> SentenceCoachOut:
    return SentenceCoachOut.model_validate(
        {"issues": issues, "explanation": explanation, "practice": []}
    )


def test_a_right_correction_passes_and_a_wrong_or_missing_one_does_not() -> None:
    right = coach([{"wrong": "ein Tisch", "correct": "einen Tisch"}])
    assert score_coach(SENTENCE, ACCEPTED, right).passed

    wrong = coach([{"wrong": "ein Tisch", "correct": "eine Tisch"}])
    score = score_coach(SENTENCE, ACCEPTED, wrong)
    assert not score.passed and score.shown == "Ich habe eine Tisch gekauft."

    assert not score_coach(SENTENCE, ACCEPTED, coach([])).passed


def test_a_correct_sentence_passes_only_if_it_is_left_alone() -> None:
    fine = "Er kann gut Deutsch sprechen."
    assert score_coach(fine, None, coach([], "No errors found.")).passed
    invented = coach([{"wrong": "gut Deutsch", "correct": "Deutsch gut"}])
    assert not score_coach(fine, None, invented).passed


def test_scoring_sees_what_the_learner_would_see_after_the_coachs_own_filters() -> None:
    # A fix with dots, and one for words that aren't in the text, never reach the learner.
    dropped = coach(
        [
            {"wrong": "ein Tisch", "correct": "einen ... Tisch"},
            {"wrong": "nicht im Text", "correct": "erfunden"},
        ]
    )
    score = score_coach(SENTENCE, ACCEPTED, dropped)
    assert not score.passed and score.shown is None


def test_no_errors_found_beside_a_correction_is_counted() -> None:
    muddled = coach([{"wrong": "ein Tisch", "correct": "einen Tisch"}], "No errors found.")
    score = score_coach(SENTENCE, ACCEPTED, muddled)
    assert score.passed and score.contradiction
    assert not score_coach(SENTENCE, ACCEPTED, coach([], "No errors found.")).contradiction


def test_exercise_answers_are_scored_with_the_fit_and_hint_checks() -> None:
    output = ExerciseHelpOut.model_validate(
        {
            "items": [
                {
                    "task": "Ich ___ aus Pakistan.",
                    "hint": "Which ending goes with ich?",
                    "answer": "Komme",
                    "filled": "Ich komme aus Pakistan.",
                },
                {
                    "task": "Wo ___ du?",
                    "hint": "Use 'wohnt'.",
                    "answer": "wohnt",
                    "filled": "Wo wohnst du?",
                },
            ]
        }
    )
    score = score_exercise(output, ["komme", "wohnst", "spricht"])
    assert (score.right, score.total, score.misfits, score.leaked_hints) == (1, 3, 1, 1)


class _PerfectModel:
    """Answers every test sentence with its accepted correction, as one whole-clause fix."""

    name = "fake"
    model = "perfect"

    async def generate(self, request: AiRequest) -> AiResponse:
        if request.user.startswith("Exercise:"):
            tasks = [
                ("Ich ___ aus Pakistan.", "komme"),
                ("Wo ___ du?", "wohnst"),
                ("Er ___ Deutsch und Englisch.", "spricht"),
                ("Wir ___ in Berlin.", "sind"),
                ("___ ihr müde?", "Seid"),
            ]
            items = [
                {
                    "task": t,
                    "hint": "Look at the subject.",
                    "answer": a,
                    "filled": t.replace("___", a),
                }
                for t, a in tasks
            ]
            return AiResponse({"items": items}, 1, 1, self.name, self.model)
        text = request.user.split("\n")[0].removeprefix("Text: ")
        accepted = dict(COACH_CASES)[text]
        issues = [{"wrong": text, "correct": sorted(accepted)[0]}] if accepted else []
        data = {"issues": issues, "explanation": "No errors found.", "practice": []}
        return AiResponse(data, 1, 1, self.name, self.model)


async def test_a_full_run_reports_a_perfect_model_as_good_enough(
    monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setattr("app.ai.evaluate.PAUSE_SECONDS", 0)
    assert await run(_PerfectModel()) is True
    report = capsys.readouterr().out
    assert f"Sentence coach: {len(COACH_CASES)} of {len(COACH_CASES)} right" in report
    assert "Exercise answers: 5 of 5 right" in report


def test_a_models_sloppy_output_is_tidied_rather_than_refused() -> None:
    # Over-long lists and text are cut, a numeric item number becomes text, an unknown task kind
    # is read as "other": one untidy field must not cost the learner the whole answer.
    coach_out = SentenceCoachOut.model_validate(
        {
            "explanation": "x" * 900,
            "issues": [{"wrong": "a", "correct": "b"}] * 5,
            "practice": ["s"] * 6,
        }
    )
    assert len(coach_out.explanation) == 500
    assert len(coach_out.issues) == 3 and len(coach_out.practice) == 3

    exercise = ExerciseHelpOut.model_validate(
        {
            "instruction": "  Fill the gaps.  ",
            "items": [{"number": 1, "task": " t ", "hint": "h" * 400, "answer": "a", "filled": ""}],
            "limits": "",
        }
    )
    (item,) = exercise.items
    assert (item.number, item.task, len(item.hint), item.filled) == ("1", "t", 200, None)
    assert exercise.instruction == "Fill the gaps." and exercise.limits is None
