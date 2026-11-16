import unicodedata
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyUrl,
    BaseModel,
    ConfigDict,
    StringConstraints,
    UrlConstraints,
    model_validator,
)

from app.core.types import UtcDatetime
from app.vocabulary.forms import Article, VerbForms, WordKind
from app.vocabulary.models import WordStage


def _nfc(text: str) -> str:
    """One form for umlauts. "ä" can arrive as one character or as "a" plus combining dots
    (pasted text, some keyboards); stored both ways, the same word would not match itself in
    reviews, searches or the dictionary."""
    return unicodedata.normalize("NFC", text)


German = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_nfc),
]
Meaning = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Sentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    AfterValidator(_nfc),
]
Short = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_nfc),
]
AudioUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["https"], max_length=2000)]


class WordFields(BaseModel):
    """Everything about a word the learner can set. Stage is not here: only reviews change it."""

    chapter_id: UUID | None = None
    dictionary_key: Short | None = None
    kind: WordKind
    german: German
    article: Article | None = None
    plural: Short | None = None
    plural_only: bool = False
    meaning_en: Meaning
    meaning_ur: Meaning | None = None
    example_sentence: Sentence | None = None
    personal_sentence: Sentence | None = None
    sentence_pattern: Short | None = None
    verb_forms: VerbForms | None = None
    source: Short | None = None
    ipa: Short | None = None
    audio_url: AudioUrl | None = None

    @model_validator(mode="after")
    def fields_match_kind(self) -> Self:
        check_kind_fields(self)
        return self


def check_kind_fields(word: "WordFields") -> None:
    if word.kind != WordKind.NOUN and (word.article or word.plural or word.plural_only):
        raise ValueError("Only nouns have an article or plural")
    if word.plural_only and word.plural:
        raise ValueError("A plural-only noun has no separate plural form")
    if word.plural_only and word.article not in (None, Article.DIE):
        raise ValueError("Plural-only nouns always take 'die'")
    if word.kind != WordKind.VERB and (word.verb_forms or word.sentence_pattern):
        raise ValueError("Only verbs have verb forms or a sentence pattern")


class WordCreate(WordFields):
    pass


class WordUpdate(BaseModel):
    """Partial update. The merged result is validated with the same rules as a new word."""

    chapter_id: UUID | None = None
    dictionary_key: Short | None = None
    kind: WordKind | None = None
    german: German | None = None
    article: Article | None = None
    plural: Short | None = None
    plural_only: bool | None = None
    meaning_en: Meaning | None = None
    meaning_ur: Meaning | None = None
    example_sentence: Sentence | None = None
    personal_sentence: Sentence | None = None
    sentence_pattern: Short | None = None
    verb_forms: VerbForms | None = None
    source: Short | None = None
    ipa: Short | None = None
    audio_url: AudioUrl | None = None


class WordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID | None
    dictionary_key: str | None
    kind: WordKind
    german: str
    article: Article | None
    plural: str | None
    plural_only: bool
    meaning_en: str
    meaning_ur: str | None
    example_sentence: str | None
    personal_sentence: str | None
    sentence_pattern: str | None
    verb_forms: VerbForms | None
    source: str | None
    ipa: str | None
    audio_url: str | None
    stage: WordStage
    created_at: UtcDatetime
