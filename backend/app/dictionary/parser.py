"""Turns one kaikki.org Wiktionary entry (one JSON line) into the few fields we store.

Format notes, from inspecting the German dump (Oct 2026):
- Entries whose senses are all `form_of` / `alt_of` are inflected forms ("Tische"): skipped.
- Noun gender is in sense tags ("masculine"/"feminine"/"neuter"); "plural-only" marks Eltern.
- Plurals are forms tagged exactly ["plural"].
- Verb present tense: forms tagged indicative+present+person+number. Separable verbs list
  main-clause forms ("stehe auf") and subordinate-clause forms ("aufstehe"); we keep main-clause.
- Glosses come as [parent, child]; parents may be headings ending in ":".
- Senses carry `examples` ({"text", "english"}); quotations have a `ref` and are skipped.
- Every inflected form of a noun, verb or adjective is kept so "gehst" and "Tische" can be looked
  up. Forms tagged "auxiliary" ("haben", "sein") are not forms of the word, and are dropped.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

KEPT_POS = {
    "noun",
    "verb",
    "adj",
    "adv",
    "pron",
    "prep",
    "conj",
    "intj",
    "num",
    "article",
    "det",
    "particle",
    "phrase",
    "prep_phrase",
    "contraction",
}

_GENDER_TAGS = {"masculine": "m", "feminine": "f", "neuter": "n"}
_GENDER_ORDER = "mfn"
_SKIPPED_SENSE_TAGS = {"obsolete", "archaic", "misspelling"}
_MAX_MEANINGS = 5

# Inflected forms: only words that inflect, and only plain words (no tables, no markup).
_FORM_POS = {"noun", "verb", "adj"}
_NOT_FORMS = {
    "auxiliary",
    "table-tags",
    "inflection-template",
    "class",
    "romanization",
    "error-unrecognized-form",
    "canonical",
    "multiword-construction",
}
_PLAIN_WORDS = re.compile(r"^[^\W\d_]+(?:[-' ][^\W\d_]+){0,2}$")
_MAX_FORM_LENGTH = 40
_MAX_FORMS = 80

_EXAMPLE_GERMAN = (12, 110)
_EXAMPLE_ENGLISH = (4, 140)

_PERSONS = {
    "ich": ("first-person", "singular"),
    "du": ("second-person", "singular"),
    "er_sie_es": ("third-person", "singular"),
    "wir": ("first-person", "plural"),
    "ihr": ("second-person", "plural"),
    "sie_Sie": ("third-person", "plural"),
}
_NOT_MAIN_PRESENT = {"subordinate-clause", "subjunctive", "subjunctive-i", "subjunctive-ii"}


@dataclass
class ParsedEntry:
    lemma: str
    pos: str
    etymology: int
    genders: list[str] = field(default_factory=list)
    plurals: list[str] = field(default_factory=list)
    plural_only: bool = False
    meanings: list[str] = field(default_factory=list)
    ipa: str | None = None
    audio_url: str | None = None
    verb_forms: dict[str, Any] | None = None
    example_de: str | None = None
    example_en: str | None = None
    forms: list[str] = field(default_factory=list)  # inflected forms, for lookup only


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def clean_gloss(gloss: str) -> str:
    """'table (a piece of furniture…); specific uses include:' -> 'table'."""
    text = gloss
    # Remove parentheticals, innermost first, so nested brackets go too.
    while True:
        stripped = re.sub(r"\s*\([^()]*\)", "", text)
        if stripped == text:
            break
        text = stripped
    text = text.split("; specific uses include")[0]
    text = re.sub(r"\s+", " ", text).strip().rstrip(":;,").strip()
    return text[:300]


def _meanings(senses: list[dict[str, Any]]) -> list[str]:
    preferred = [s for s in senses if not _SKIPPED_SENSE_TAGS & set(s.get("tags", []))]
    out = []
    for sense in preferred or senses:
        glosses = sense.get("glosses") or []
        if not glosses:
            continue
        cleaned = clean_gloss(glosses[0])
        if not cleaned and len(glosses) > 1:
            cleaned = clean_gloss(glosses[-1])
        if cleaned:
            out.append(cleaned)
    return _dedupe(out)[:_MAX_MEANINGS]


def _verb_forms(forms: list[dict[str, Any]]) -> dict[str, Any] | None:
    present: dict[str, str] = {}
    preterite = past_participle = None
    auxiliaries: list[str] = []

    for f in forms:
        form = _nfc(f.get("form", ""))
        tags = f.get("tags") or []
        if not form:
            continue
        tagset = set(tags)
        if tags == ["past"] and preterite is None:
            preterite = form
        elif tagset == {"participle", "past"} and past_participle is None:
            past_participle = form
        elif tags == ["auxiliary"]:
            auxiliaries.extend(a.strip() for a in form.split(" or "))
        elif {"indicative", "present"} <= tagset and not tagset & _NOT_MAIN_PRESENT:
            for person, needed in _PERSONS.items():
                if person not in present and set(needed) <= tagset:
                    present[person] = form

    aux = [a for a in ("haben", "sein") if a in auxiliaries]
    if not present and not past_participle:
        return None
    return {
        "present": present,
        "preterite": preterite,
        "past_participle": past_participle,
        "auxiliary": "/".join(aux) or None,
        "separable": " " in present.get("ich", ""),
    }


def _example(senses: list[dict[str, Any]]) -> tuple[str, str] | None:
    """The shortest real example sentence, with its English translation, from the first sense
    that has one (senses are listed most common first, so the example fits the first meaning)."""
    for sense in senses:
        best: tuple[str, str] | None = None
        for ex in sense.get("examples") or []:
            if ex.get("ref") or ex.get("type") == "quotation":
                continue  # a quotation from a book, not a model sentence
            german = _nfc(str(ex.get("text") or ""))
            english = _nfc(str(ex.get("english") or ex.get("translation") or ""))
            if not (_EXAMPLE_GERMAN[0] <= len(german) <= _EXAMPLE_GERMAN[1]):
                continue
            if not (_EXAMPLE_ENGLISH[0] <= len(english) <= _EXAMPLE_ENGLISH[1]):
                continue
            if "[" in german or "[" in english:
                continue  # editorial brackets
            if best is None or len(german) < len(best[0]):
                best = (german, english)
        if best:
            return best
    return None


def _inflected_forms(forms: list[dict[str, Any]], lemma: str) -> list[str]:
    out: list[str] = []
    seen = {lemma.lower()}
    for f in forms:
        if _NOT_FORMS & set(f.get("tags") or []):
            continue
        form = _nfc(str(f.get("form") or ""))
        if not form or len(form) > _MAX_FORM_LENGTH or not _PLAIN_WORDS.match(form):
            continue
        key = form.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(form)
        if len(out) >= _MAX_FORMS:
            break
    return out


def parse_entry(raw: dict[str, Any]) -> ParsedEntry | None:
    if raw.get("lang_code") != "de" or raw.get("pos") not in KEPT_POS:
        return None
    lemma = _nfc(raw.get("word", ""))
    if not lemma or len(lemma) > 200:
        return None

    senses = [
        s
        for s in raw.get("senses", [])
        if "form_of" not in s and "alt_of" not in s and s.get("glosses")
    ]
    if not senses:
        return None  # an inflected form or an alternative spelling

    entry = ParsedEntry(
        lemma=lemma,
        pos=raw["pos"],
        etymology=int(raw.get("etymology_number") or 0),
        meanings=_meanings(senses),
    )
    if not entry.meanings:
        return None

    sense_tags = {t for s in senses for t in s.get("tags", [])}
    forms = raw.get("forms") or []

    if entry.pos == "noun":
        genders = {_GENDER_TAGS[t] for t in sense_tags if t in _GENDER_TAGS}
        entry.genders = sorted(genders, key=_GENDER_ORDER.index)
        entry.plural_only = "plural-only" in sense_tags
        if not entry.plural_only:
            entry.plurals = _dedupe(
                [_nfc(f["form"]) for f in forms if f.get("tags") == ["plural"] and f.get("form")]
            )
            entry.plurals = [p for p in entry.plurals if p not in {"-", "—"} and len(p) <= 200]
    elif entry.pos == "verb":
        entry.verb_forms = _verb_forms(forms)

    example = _example(senses)
    if example:
        entry.example_de, entry.example_en = example
    if entry.pos in _FORM_POS:
        entry.forms = _inflected_forms(forms, lemma)

    for sound in raw.get("sounds") or []:
        if entry.ipa is None and sound.get("ipa"):
            entry.ipa = str(sound["ipa"])[:200]
        url = sound.get("mp3_url")
        if entry.audio_url is None and isinstance(url, str) and url.startswith("https://"):
            entry.audio_url = url

    return entry
