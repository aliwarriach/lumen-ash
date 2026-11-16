"""Our own A1 rules: the part of the coach that decides what counts as "Confirmed".

LanguageTool says where something looks wrong and suggests a fix. Here we map its rule to one of
our grammar patterns and check the suggested fix against the dictionary (gender, plural, verb
forms). Only when the two agree is a correction Confirmed. Nothing here calls the AI.

Every verifier is deliberately narrow: it returns a reason only when it is sure, and says nothing
otherwise. When the dictionary is missing or a word is ambiguous (several genders), nothing is
confirmed.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey

_TOKEN = re.compile(r"[\wäöüßÄÖÜ]+")

GENDER_NAMES = {"m": "masculine", "f": "feminine", "n": "neuter"}
DEFINITE = {"m": "der", "f": "die", "n": "das"}
# Every article form (all cases) that can go with a noun of each gender, singular.
ARTICLE_FORMS = {
    "m": frozenset({"der", "den", "dem", "des", "ein", "einen", "einem", "eines"}),
    "f": frozenset({"die", "der", "eine", "einer"}),
    "n": frozenset({"das", "dem", "des", "ein", "einem", "eines"}),
}
# Nominative -> accusative for the masculine article, "kein" and the possessives.
NOMINATIVE_TO_ACCUSATIVE = {
    "der": "den",
    "ein": "einen",
    "kein": "keinen",
    "mein": "meinen",
    "dein": "deinen",
    "sein": "seinen",
    "ihr": "ihren",
    "unser": "unseren",
    "euer": "euren",
}
PRONOUN_KEYS = {
    "ich": ("ich",),
    "du": ("du",),
    "er": ("er_sie_es",),
    "es": ("er_sie_es",),
    "sie": ("er_sie_es", "sie_Sie"),  # she / they: both forms are possible
    "wir": ("wir",),
    "ihr": ("ihr",),
}


@dataclass(frozen=True)
class NounInfo:
    lemma: str
    genders: frozenset[str]
    plurals: frozenset[str]


@dataclass(frozen=True)
class VerbInfo:
    lemma: str
    present: Mapping[str, str]  # "ich" / "du" / "er_sie_es" / ... -> form


@dataclass(frozen=True)
class DictData:
    """The dictionary entries for the words a correction touches, keyed by lowercase lemma."""

    nouns: Mapping[str, NounInfo] = field(default_factory=dict)
    verbs: Mapping[str, VerbInfo] = field(default_factory=dict)


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def words_to_look_up(*texts: str) -> set[str]:
    return {t.lower() for text in texts for t in tokens(text)}


# --- LanguageTool rule -> our pattern ---


def map_rule(rule_id: str, category: str) -> tuple[PatternKey | None, MistakeCategory]:
    """The grammar pattern a LanguageTool rule is about, and the mistake-log category."""
    pattern: PatternKey | None = None
    if rule_id == "OBJECT_AGREEMENT":
        pattern = PatternKey.ACCUSATIVE
    elif rule_id.startswith(("SIMPLE_AGREEMENT", "DE_AGREEMENT")):
        pattern = PatternKey.NOUN_GENDER
    elif (
        rule_id in {"UPPERCASE_SENTENCE_START", "KANN_ENGLISCH", "DE_CASE"} or category == "CASING"
    ):
        pattern = PatternKey.CAPITALS_SPELLING
    elif rule_id == "VIELZAHL_PLUS_SINGULAR":
        pattern = PatternKey.PLURAL_FORMS
    elif rule_id == "DE_VERBAGREEMENT":
        pattern = PatternKey.PRESENT_ENDINGS
    elif rule_id == "HILFSVERB_HABEN_SEIN":
        pattern = PatternKey.SEIN_HABEN
    if pattern is not None:
        return pattern, PATTERNS[pattern].category
    if category == "TYPOS":
        return None, MistakeCategory.SPELLING
    return None, MistakeCategory.OTHER


# --- Verifiers: does the dictionary agree with the suggested fix? Each returns a reason or None ---


def _accusative(wrong: str, right: str, data: DictData) -> str | None:
    w, r = tokens(wrong), tokens(right)
    if len(w) != 2 or len(r) != 2 or w[1] != r[1]:
        return None
    expected = NOMINATIVE_TO_ACCUSATIVE.get(w[0].lower())
    noun = data.nouns.get(w[1].lower())
    if expected is None or r[0].lower() != expected or noun is None or noun.genders != {"m"}:
        return None
    return (
        f"{noun.lemma} is masculine (der {noun.lemma}). When it is the object of the verb, "
        f"a masculine noun takes the accusative: {r[0]} {r[1]}, not {w[0]} {w[1]}."
    )


def _noun_gender(wrong: str, right: str, data: DictData) -> str | None:
    w, r = tokens(wrong), tokens(right)
    if len(w) != 2 or len(r) != 2 or w[1] != r[1]:
        return None
    noun = data.nouns.get(w[1].lower())
    if noun is None or len(noun.genders) != 1:
        return None
    (gender,) = noun.genders
    valid = ARTICLE_FORMS[gender]
    if w[0].lower() in valid or r[0].lower() not in valid:
        return None
    return (
        f"{noun.lemma} is {GENDER_NAMES[gender]}: {DEFINITE[gender]} {noun.lemma}. "
        f"Learn every noun together with its article."
    )


def _capitals(wrong: str, right: str, data: DictData, sentence_start: bool) -> str | None:
    w, r = tokens(wrong), tokens(right)
    if len(w) != 1 or len(r) != 1 or w[0] == r[0] or w[0].lower() != r[0].lower():
        return None
    noun = data.nouns.get(r[0].lower())
    if r[0][0].isupper():
        if noun is not None and noun.lemma == r[0]:
            return f"{r[0]} is a noun, so it starts with a capital letter."
        if sentence_start:
            return "A sentence starts with a capital letter."
        return None
    # Capital -> small: only if it is not a noun, and not the first word of a sentence.
    if sentence_start or (noun is not None and noun.lemma == w[0]):
        return None
    return f"{r[0]} is not a noun, so it is written with a small letter."


def _plural(wrong: str, right: str, data: DictData) -> str | None:
    w, r = tokens(wrong), tokens(right)
    if len(w) != 1 or len(r) != 1:
        return None
    noun = data.nouns.get(w[0].lower())
    if noun is None or r[0] not in noun.plurals or w[0] in noun.plurals:
        return None
    return f"After a number above one the noun is plural: die {r[0]} (singular: {noun.lemma})."


def _present_endings(wrong: str, right: str, data: DictData) -> str | None:
    w, r = tokens(wrong), tokens(right)
    if len(w) != 2 or len(r) != 2 or w[0].lower() != r[0].lower():
        return None
    keys = PRONOUN_KEYS.get(w[0].lower())
    verb = data.verbs.get(w[1].lower())  # works when the wrong form is the infinitive
    if keys is None or verb is None:
        return None
    forms = {verb.present[k] for k in keys if verb.present.get(k)}
    if r[1] not in forms or w[1] in forms:
        return None
    return (
        f"With '{w[0]}' the verb takes the ending of the person, not the infinitive: "
        f"{r[0]} {r[1]} (from {verb.lemma})."
    )


def verify(
    pattern: PatternKey | None, wrong: str, right: str, data: DictData, *, sentence_start: bool
) -> str | None:
    """A plain-English reason if our rules agree that `right` is the correct fix, else None."""
    match pattern:
        case PatternKey.ACCUSATIVE:
            return _accusative(wrong, right, data)
        case PatternKey.NOUN_GENDER:
            return _noun_gender(wrong, right, data)
        case PatternKey.CAPITALS_SPELLING:
            return _capitals(wrong, right, data, sentence_start)
        case PatternKey.PLURAL_FORMS:
            return _plural(wrong, right, data)
        case PatternKey.PRESENT_ENDINGS:
            return _present_endings(wrong, right, data)
        case _:
            return None
