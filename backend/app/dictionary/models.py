from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DictionaryEntry(Base):
    """Reference word data imported from Wiktionary (via kaikki.org). Shared by all users.

    Licensed CC BY-SA: the app must show attribution wherever this data appears.
    """

    __tablename__ = "dictionary_entries"
    __table_args__ = (
        # One index serves both exact lookups and prefix (autocomplete) searches.
        Index(
            "ix_dictionary_entries_lemma_lower",
            "lemma_lower",
            postgresql_ops={"lemma_lower": "varchar_pattern_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Stable identity across re-imports: "<word>|<pos>|<etymology>|<occurrence>".
    source_key: Mapped[str] = mapped_column(String(300), unique=True)
    lemma: Mapped[str] = mapped_column(String(200))
    lemma_lower: Mapped[str] = mapped_column(String(200))
    pos: Mapped[str] = mapped_column(String(20))  # Wiktionary part of speech: noun, verb, adj...
    genders: Mapped[list[str]] = mapped_column(ARRAY(String(1)))  # "m", "f", "n"
    plurals: Mapped[list[str]] = mapped_column(ARRAY(String(200)))
    plural_only: Mapped[bool] = mapped_column(server_default="false")  # e.g. die Eltern
    meanings: Mapped[list[str]] = mapped_column(ARRAY(Text))  # English glosses
    ipa: Mapped[str | None] = mapped_column(String(200))
    audio_url: Mapped[str | None] = mapped_column(Text)  # Wikimedia Commons recording
    verb_forms: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # One real example sentence (Wiktionary) and its English translation.
    example_de: Mapped[str | None] = mapped_column(Text)
    example_en: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DictionaryForm(Base):
    """An inflected form of a dictionary entry ("gehst" -> gehen), so a form can be looked up.

    Shared by all users and rebuilt on every import. The key (form, entry) serves the lookup.
    """

    __tablename__ = "dictionary_forms"

    form_lower: Mapped[str] = mapped_column(String(60), primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("dictionary_entries.id", ondelete="CASCADE"), primary_key=True
    )
