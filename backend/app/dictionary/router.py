import re
import unicodedata
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.dictionary.models import DictionaryEntry, DictionaryForm
from app.vocabulary.forms import GENDER_TO_ARTICLE, Article, VerbForms, WordKind
from app.vocabulary.models import VocabWord

router = APIRouter(tags=["dictionary"])

ATTRIBUTION = "Word data from Wiktionary (CC BY-SA 4.0), via kaikki.org"

_POS_TO_KIND = {
    "noun": WordKind.NOUN,
    "verb": WordKind.VERB,
    "adj": WordKind.ADJECTIVE,
    "adv": WordKind.ADVERB,
    "phrase": WordKind.PHRASE,
    "prep_phrase": WordKind.PHRASE,
}
# Most useful first when one spelling has several entries.
_POS_ORDER = ["noun", "verb", "adj", "adv", "prep", "pron", "conj", "num", "article", "det"]
_LEADING_ARTICLE = re.compile(r"^(der|die|das|ein|eine)\s+", re.IGNORECASE)


class DictionaryEntryOut(BaseModel):
    key: str
    lemma: str
    pos: str
    kind: WordKind
    articles: list[Article]
    plurals: list[str]
    plural_only: bool
    meanings: list[str]
    ipa: str | None
    audio_url: str | None
    verb_forms: VerbForms | None
    example_de: str | None
    example_en: str | None
    wiktionary_url: str


class SavedWordRef(BaseModel):
    id: str
    kind: WordKind
    german: str
    meaning_en: str


class LookupOut(BaseModel):
    query: str
    entries: list[DictionaryEntryOut]
    # Set when the query was an inflected form ("gehst") and `entries` are the words it belongs to.
    matched_form: str | None = None
    suggestions: list[str]
    saved: list[SavedWordRef]
    attribution: str


def normalize_query(q: str) -> str:
    """'  der Tisch ' -> 'Tisch'."""
    text = unicodedata.normalize("NFC", q).strip()
    return _LEADING_ARTICLE.sub("", text).strip()


def _entry_out(e: DictionaryEntry) -> DictionaryEntryOut:
    return DictionaryEntryOut(
        key=e.source_key,
        lemma=e.lemma,
        pos=e.pos,
        kind=_POS_TO_KIND.get(e.pos, WordKind.OTHER),
        articles=[Article.DIE] if e.plural_only else [GENDER_TO_ARTICLE[g] for g in e.genders],
        plurals=e.plurals,
        plural_only=e.plural_only,
        meanings=e.meanings,
        ipa=e.ipa,
        audio_url=e.audio_url,
        verb_forms=VerbForms.model_validate(e.verb_forms) if e.verb_forms else None,
        example_de=e.example_de,
        example_en=e.example_en,
        wiktionary_url=f"https://en.wiktionary.org/wiki/{quote(e.lemma)}#German",
    )


def _case_match(query: str) -> Any:
    """Sort key: entries written in the same case as the query (lower or capitalised) first."""
    lemma_is_lower = DictionaryEntry.lemma == func.lower(DictionaryEntry.lemma)
    if query[:1].islower():
        return case((lemma_is_lower, 0), else_=1)
    return case((lemma_is_lower, 1), else_=0)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@router.get("/dictionary/lookup")
async def lookup(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    user: CurrentUserDep,
    session: SessionDep,
) -> LookupOut:
    """Finds a word, with autocomplete suggestions and the learner's own saved copies."""
    query = normalize_query(q)
    lower = query.lower()
    if not lower:
        return LookupOut(query=query, entries=[], suggestions=[], saved=[], attribution=ATTRIBUTION)

    pos_rank = case(
        {pos: i for i, pos in enumerate(_POS_ORDER)},
        value=DictionaryEntry.pos,
        else_=len(_POS_ORDER),
    )
    entries = list(
        await session.scalars(
            select(DictionaryEntry)
            .where(DictionaryEntry.lemma_lower == lower)
            # "Essen" -> the noun first; "essen" -> the verb first.
            .order_by(
                case((DictionaryEntry.lemma == query, 0), else_=1),
                pos_rank,
                DictionaryEntry.source_key,
            )
            .limit(10)
        )
    )
    matched_form: str | None = None
    if not entries:
        # Not a headword: maybe an inflected form ("gehst" -> gehen, "Tische" -> Tisch).
        entries = list(
            await session.scalars(
                select(DictionaryEntry)
                .join(DictionaryForm, DictionaryForm.entry_id == DictionaryEntry.id)
                .where(DictionaryForm.form_lower == lower)
                # German nouns are capitalised, so "kleine" means klein, and "Kleine" the noun.
                .order_by(
                    _case_match(query),
                    pos_rank,
                    func.length(DictionaryEntry.lemma),
                    DictionaryEntry.source_key,
                )
                .limit(10)
            )
        )
        if entries:
            matched_form = query

    suggestions: list[str] = []
    if len(lower) >= 2:
        rows = await session.scalars(
            select(DictionaryEntry.lemma)
            .where(
                DictionaryEntry.lemma_lower.like(_escape_like(lower) + "%"),
                DictionaryEntry.lemma_lower != lower,
            )
            .group_by(DictionaryEntry.lemma)
            .order_by(func.length(DictionaryEntry.lemma), DictionaryEntry.lemma)
            .limit(8)
        )
        suggestions = list(rows)

    saved = await session.scalars(
        select(VocabWord).where(VocabWord.user_id == user.id, func.lower(VocabWord.german) == lower)
    )
    return LookupOut(
        query=query,
        entries=[_entry_out(e) for e in entries],
        matched_form=matched_form,
        suggestions=suggestions,
        saved=[
            SavedWordRef(id=str(w.id), kind=w.kind, german=w.german, meaning_en=w.meaning_en)
            for w in saved
        ],
        attribution=ATTRIBUTION,
    )
