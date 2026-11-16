from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, OwnedMixin
from app.vocabulary.forms import Article, WordKind


class WordStage(StrEnum):
    """Moves forward only on evidence from reviews (Phase 3), never by hand."""

    NEW = "new"
    LEARNING = "learning"
    FAMILIAR = "familiar"
    USABLE = "usable"
    MASTERED = "mastered"


def _str_enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [m.value for m in members],
        name=name,
    )


class VocabWord(OwnedMixin, Base):
    __tablename__ = "vocab_words"

    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    # Which dictionary entry the word was filled from, if any. Data is copied, not linked,
    # so re-importing the dictionary never changes a learner's saved word.
    dictionary_key: Mapped[str | None] = mapped_column(String(300))

    kind: Mapped[WordKind] = mapped_column(_str_enum(WordKind, "word_kind"))
    german: Mapped[str] = mapped_column(String(200))  # without the article
    article: Mapped[Article | None] = mapped_column(_str_enum(Article, "word_article"))
    plural: Mapped[str | None] = mapped_column(String(200))
    plural_only: Mapped[bool] = mapped_column(default=False, server_default="false")
    meaning_en: Mapped[str] = mapped_column(String(300))
    meaning_ur: Mapped[str | None] = mapped_column(String(300))
    example_sentence: Mapped[str | None] = mapped_column(Text)
    personal_sentence: Mapped[str | None] = mapped_column(Text)
    sentence_pattern: Mapped[str | None] = mapped_column(String(200))  # verbs: "jemanden fragen"
    verb_forms: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source: Mapped[str | None] = mapped_column(String(200))  # e.g. "Netzwerk S. 24"
    ipa: Mapped[str | None] = mapped_column(String(200))
    audio_url: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[WordStage] = mapped_column(
        _str_enum(WordStage, "word_stage"), default=WordStage.NEW, server_default="new"
    )
