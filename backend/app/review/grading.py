"""Checks typed answers. Deliberately strict where German is strict (articles, noun capitals)
and lenient about things that aren't German skills (spacing, final punctuation, quote styles).

The app mirrors these rules (app/src/features/review/grading.ts) for instant offline feedback;
the server's result is the one that counts.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.grammar.catalog import PatternKey
from app.vocabulary.forms import Article, WordKind
from app.vocabulary.models import VocabWord


@dataclass(frozen=True)
class Grade:
    correct: bool
    expected: str
    feedback: str | None = None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".!?").strip()


def expected_answer(word: VocabWord) -> str:
    """What the learner should type for a produce card: 'der Tisch', 'die Eltern', 'gehen'."""
    if word.kind == WordKind.NOUN:
        article = Article.DIE if word.plural_only else word.article
        if article:
            return f"{article} {word.german}"
    return word.german


UMLAUT_TIP = (
    "Check ä, ö, ü and ß: they are letters of their own. "
    "Hold a, o, u or s on the keyboard to type them."
)
_WITHOUT_DOTS = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})
_SPELLED_OUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def only_umlauts_differ(given: str, expected: str) -> bool:
    """The answer is the expected text with an umlaut or ß left out or spelled out: "Madchen" or
    "Maedchen" for Mädchen, "Strasse" for Straße, "Mutter" for the plural Mütter.

    Still a wrong answer (Mutter and Mütter are different words), but one that deserves to be
    told exactly what is wrong. Both arguments must already be normalised."""
    g, e = given.lower(), expected.lower()
    if g == e or not any(c in e for c in "äöüß"):
        return False
    return g == e.translate(_SPELLED_OUT) or g.translate(_WITHOUT_DOTS) == e.translate(
        _WITHOUT_DOTS
    )


def check_produce(word: VocabWord, answer: str) -> Grade:
    shown = expected_answer(word)
    # Both sides in the same Unicode form: "ä" can be stored as one character or as a + dots.
    expected = normalize(shown)
    given = normalize(answer)
    if given == expected:
        return Grade(True, shown)

    feedback = None
    if given.lower() == expected.lower():
        feedback = "Check the capital letters: German nouns start with a capital."
    elif only_umlauts_differ(given, expected):
        feedback = UMLAUT_TIP
    elif word.kind == WordKind.NOUN and " " in expected:
        article, _, noun = expected.partition(" ")
        given_article, _, given_noun = given.partition(" ")
        missing_article = given == noun or (
            given_noun == noun and given_article not in {"der", "die", "das"}
        )
        if missing_article:
            feedback = f"Include the article: {article}."
        elif given_noun == noun:
            feedback = f"Wrong article: it's {article} {noun}."
    return Grade(False, shown, feedback)


def _article_parts(
    word: VocabWord, article: str | None, plural: str | None
) -> tuple[Article | None, bool | None, bool | None]:
    """(expected article, article right?, plural right?). None where the card doesn't ask."""
    expected_article = Article.DIE if word.plural_only else word.article
    article_ok = (article or "").strip().lower() == expected_article if expected_article else None
    asks_plural = bool(word.plural) and not word.plural_only
    plural_ok = normalize(plural or "") == normalize(word.plural or "") if asks_plural else None
    return expected_article, article_ok, plural_ok


def check_article(word: VocabWord, article: str | None, plural: str | None) -> Grade:
    expected_article, article_ok, plural_ok = _article_parts(word, article, plural)
    parts = [f"{expected_article} {word.german}" if expected_article else word.german]
    if plural_ok is not None:
        parts.append(f"die {word.plural}")
    expected = " · ".join(parts)

    problems = []
    if article_ok is False:
        problems.append(f"The article is {expected_article}.")
    if plural_ok is False:
        problems.append(f"The plural is die {word.plural}.")
        if only_umlauts_differ(normalize(plural or ""), normalize(word.plural or "")):
            problems.append(UMLAUT_TIP)
    return Grade(not problems, expected, " ".join(problems) or None)


def check_correction(correct: str, answer: str) -> Grade:
    """Error-retry cards: the learner writes the corrected version of a logged mistake."""
    given, expected = normalize(answer), normalize(correct)
    if given == expected:
        return Grade(True, correct)
    feedback = None
    if given.lower() == expected.lower():
        feedback = "Check the capital letters."
    elif only_umlauts_differ(given, expected):
        feedback = UMLAUT_TIP
    elif given.split() and sorted(given.split()) == sorted(expected.split()):
        feedback = "The right words, but in the wrong order."
    return Grade(False, correct, feedback)


# --- Grammar evidence: which patterns an answer shows the learner can or can't use ---


def article_evidence(
    word: VocabWord, article: str | None, plural: str | None
) -> dict[PatternKey, bool]:
    _, article_ok, plural_ok = _article_parts(word, article, plural)
    evidence = {}
    if article_ok is not None:
        evidence[PatternKey.NOUN_GENDER] = article_ok
    if plural_ok is not None:
        evidence[PatternKey.PLURAL_FORMS] = plural_ok
    return evidence


def produce_evidence(word: VocabWord, answer: str) -> dict[PatternKey, bool]:
    """A typed noun counts for gender only if the noun itself is right: 'das Tisch' is a gender
    mistake, 'der Stuhl' (for Tisch) is a vocabulary one."""
    expected = normalize(expected_answer(word))
    if word.kind != WordKind.NOUN or " " not in expected:
        return {}
    article, _, noun = expected.partition(" ")
    given_article, _, given_noun = normalize(answer).partition(" ")
    if given_noun != noun or given_article.lower() not in {"der", "die", "das"}:
        return {}
    return {PatternKey.NOUN_GENDER: given_article.lower() == article}


def word_forms(word: VocabWord) -> list[list[str]]:
    """Forms that count as 'using the word'. Each form is a list of tokens that must all appear,
    so a separable verb ('stehe auf') counts when both parts are in the sentence."""
    forms = {word.german}
    if word.plural:
        forms.add(word.plural)
    vf = word.verb_forms or {}
    forms.update(v for v in (vf.get("present") or {}).values() if v)
    for key in ("past_participle", "preterite"):
        if vf.get(key):
            forms.add(vf[key])
    return [f.lower().split() for f in forms if f.strip()]


def uses_word(word: VocabWord, sentence: str) -> bool:
    tokens = set(re.findall(r"[\wäöüß]+", unicodedata.normalize("NFC", sentence).lower()))
    return any(all(t in tokens for t in form) for form in word_forms(word))
