"""Umlauts and ß in typed answers. The app mirrors these rules (app/tests/grading.test.ts)."""

import unicodedata

import pytest

from app.grammar.catalog import PatternKey
from app.review.grading import (
    UMLAUT_TIP,
    check_article,
    check_correction,
    check_produce,
    only_umlauts_differ,
    produce_evidence,
)
from app.vocabulary.forms import Article, WordKind
from app.vocabulary.models import VocabWord
from app.vocabulary.schemas import WordCreate

MAEDCHEN = VocabWord(
    kind=WordKind.NOUN, german="Mädchen", article=Article.DAS, plural="Mädchen", plural_only=False
)
STRASSE = VocabWord(
    kind=WordKind.NOUN, german="Straße", article=Article.DIE, plural="Straßen", plural_only=False
)
MUTTER = VocabWord(
    kind=WordKind.NOUN, german="Mutter", article=Article.DIE, plural="Mütter", plural_only=False
)


@pytest.mark.parametrize(
    ("given", "expected", "only_umlauts"),
    [
        ("das Madchen", "das Mädchen", True),  # dots left off
        ("das Maedchen", "das Mädchen", True),  # spelled out
        ("die Strasse", "die Straße", True),
        ("Mutter", "Mütter", True),
        ("Fussball", "Fußball", True),
        ("schoen", "schön", True),
        ("das Mädchen", "das Mädchen", False),  # right
        ("das Madchin", "das Mädchen", False),  # another mistake as well
        ("der Tisch", "der Tisch", False),
        ("der Tüsch", "der Tisch", False),  # an umlaut that doesn't belong is not this mistake
    ],
)
def test_telling_an_umlaut_slip_from_another_mistake(
    given: str, expected: str, only_umlauts: bool
) -> None:
    assert only_umlauts_differ(given, expected) is only_umlauts


def test_a_missing_umlaut_is_still_wrong_but_says_exactly_what_to_check() -> None:
    for answer in ("das Madchen", "das Maedchen"):
        grade = check_produce(MAEDCHEN, answer)
        assert (grade.correct, grade.expected, grade.feedback) == (False, "das Mädchen", UMLAUT_TIP)
    assert check_produce(STRASSE, "die Strasse").feedback == UMLAUT_TIP
    assert check_produce(MAEDCHEN, "das Mädchen").correct
    # Other feedback is unchanged.
    assert "capital" in (check_produce(MAEDCHEN, "das mädchen").feedback or "")
    assert check_produce(MAEDCHEN, "der Mädchen").feedback == "Wrong article: it's das Mädchen."


def test_a_plural_that_only_lacks_its_umlaut_gets_the_tip_too() -> None:
    grade = check_article(MUTTER, "die", "Mutter")
    assert not grade.correct
    assert grade.feedback == f"The plural is die Mütter. {UMLAUT_TIP}"
    assert check_article(MUTTER, "die", "Muttern").feedback == "The plural is die Mütter."
    assert check_article(MUTTER, "die", "Mütter").correct


def test_a_retried_mistake_gets_the_tip() -> None:
    assert check_correction("Ich heiße Ali.", "Ich heisse Ali.").feedback == UMLAUT_TIP
    assert check_correction("Ich heiße Ali.", "Ich heiße Ali").correct


def test_the_same_letters_in_another_unicode_form_are_the_same_answer() -> None:
    # "ä" as one character (NFC) and as "a" + combining dots (NFD) look identical on screen.
    decomposed = unicodedata.normalize("NFD", "Mädchen")
    assert decomposed != "Mädchen"
    stored_decomposed = VocabWord(
        kind=WordKind.NOUN,
        german=decomposed,
        article=Article.DAS,
        plural=unicodedata.normalize("NFD", "Mütter"),
        plural_only=False,
    )
    assert check_produce(stored_decomposed, "das Mädchen").correct
    assert check_produce(MAEDCHEN, f"das {decomposed}").correct
    assert check_article(stored_decomposed, "das", "Mütter").correct
    assert produce_evidence(stored_decomposed, "das Mädchen") == {PatternKey.NOUN_GENDER: True}


def test_new_words_are_saved_in_one_unicode_form() -> None:
    decomposed = unicodedata.normalize("NFD", "Mädchen")
    word = WordCreate(
        kind=WordKind.NOUN,
        german=decomposed,
        article=Article.DAS,
        plural=unicodedata.normalize("NFD", "Mütter"),
        meaning_en="girl",
        example_sentence=unicodedata.normalize("NFD", "Das Mädchen ist müde."),
    )
    assert (word.german, word.plural) == ("Mädchen", "Mütter")
    assert word.example_sentence == "Das Mädchen ist müde."
