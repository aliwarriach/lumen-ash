"""Shared word shapes used by both the dictionary and the learner's own words."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, StringConstraints

Form = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WordKind(StrEnum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PHRASE = "phrase"
    OTHER = "other"


class Article(StrEnum):
    DER = "der"
    DIE = "die"
    DAS = "das"


GENDER_TO_ARTICLE = {"m": Article.DER, "f": Article.DIE, "n": Article.DAS}


class PresentTense(BaseModel):
    ich: Form | None = None
    du: Form | None = None
    er_sie_es: Form | None = None
    wir: Form | None = None
    ihr: Form | None = None
    sie_Sie: Form | None = None


class VerbForms(BaseModel):
    present: PresentTense = PresentTense()
    preterite: Form | None = None  # er/sie/es form, e.g. "ging"
    past_participle: Form | None = None  # e.g. "gegangen"
    auxiliary: Form | None = None  # "haben", "sein" or "haben/sein"
    separable: bool = False  # aufstehen -> "ich stehe auf"
