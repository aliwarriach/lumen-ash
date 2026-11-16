"""Does an AI answer fit the exercise as printed, and does its hint keep the answer back?"""

import pytest

from app.scanner.verify import answer_in_sentence, hint_gives_answer, sentence_matches_task


@pytest.mark.parametrize(
    ("answer", "filled", "fits"),
    [
        ("komme", "Ich komme aus Pakistan.", True),
        ("Seid", "Seid ihr müde?", True),
        ("kauft einen", "Er kauft einen Tisch.", True),
        ("stehe auf", "Ich stehe um 6 Uhr auf.", True),  # the two parts need not be neighbours
        ("auf stehe", "Ich stehe um 6 Uhr auf.", False),  # but they must come in this order
        ("kommst", "Ich komme aus Pakistan.", False),
        ("", "Ich komme aus Pakistan.", False),
    ],
)
def test_the_answer_must_be_in_the_filled_in_sentence(answer: str, filled: str, fits: bool) -> None:
    assert answer_in_sentence(answer, filled) is fits


@pytest.mark.parametrize(
    ("task", "filled", "matches"),
    [
        ("Ich ___ aus Pakistan. (kommen)", "Ich komme aus Pakistan.", True),
        ("1 Ich ___ aus Pakistan. (kommen)", "Ich komme aus Pakistan.", True),
        ("a) Wo ___ du? (wohnen)", "Wo wohnst du?", True),
        ("___ ihr müde?", "Seid ihr müde?", True),
        ("Er ..... Deutsch und Englisch.", "Er spricht Deutsch und Englisch.", True),
        ("Das ist ___ Tisch. ___ Tisch ist neu.", "Das ist ein Tisch. Der Tisch ist neu.", True),
        # The AI wrote a different sentence.
        ("Ich ___ aus Pakistan.", "Ich wohne in Berlin.", False),
        ("Wo ___ du?", "Wie heißt du?", False),
        # One misread word in a longer line is forgiven: the AI put the photo's mistake right.
        ("lch ___ jeden Tag um 7 Uhr auf.", "Ich stehe jeden Tag um 7 Uhr auf.", True),
        ("lch ___ jedem Tog um 7 Uhr auf.", "Ich stehe jeden Tag um 7 Uhr auf.", False),
        # No gap printed: nothing to compare.
        ("du / wohnen / wo", "Wo wohnst du?", None),
        ("___", "Hallo!", None),
    ],
)
def test_the_filled_in_sentence_must_be_the_printed_line(
    task: str, filled: str, matches: bool | None
) -> None:
    assert sentence_matches_task(task, filled) is matches


@pytest.mark.parametrize(
    ("hint", "answer", "gives_away"),
    [
        ("Use 'komme', the ich form.", "komme", True),
        ("The ich form of kommen is komme.", "komme", True),
        ("Which ending goes with 'ich'?", "komme", False),
        ("Think about the verb in brackets: kommen.", "komme", False),  # the infinitive is printed
        # Short answers are also English words, so they count only when quoted.
        ("Which preposition is used for being in a city?", "in", False),
        ("Use 'in' for cities.", "in", True),
        ("The article is „die“.", "die", True),
        ("Verbs can die out.", "die", False),
        ("Both parts: stehe at position two, auf at the end.", "stehe auf", False),
        ("Write 'stehe' second and 'auf' last.", "stehe auf", True),
        ("Anything.", "", False),
    ],
)
def test_a_hint_must_not_contain_the_answer(hint: str, answer: str, gives_away: bool) -> None:
    assert hint_gives_answer(hint, answer) is gives_away
