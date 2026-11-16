"""The importer, run on a tiny file in the shape of the kaikki.org dump."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, func, select

from app.dictionary.importer import import_file
from app.dictionary.models import DictionaryEntry, DictionaryForm

TISCH = {
    "word": "Tisch",
    "pos": "noun",
    "lang_code": "de",
    "senses": [
        {
            "glosses": ["table"],
            "tags": ["masculine"],
            "examples": [{"text": "Der Tisch ist gedeckt.", "english": "The table is set."}],
        }
    ],
    "forms": [{"form": "Tische", "tags": ["plural"]}, {"form": "Tisches", "tags": ["genitive"]}],
}
GEHEN = {
    "word": "gehen",
    "pos": "verb",
    "lang_code": "de",
    "senses": [{"glosses": ["to go"]}],
    "forms": [{"form": "gehst", "tags": ["indicative", "present", "second-person", "singular"]}],
}
FORM_ONLY = {  # an inflected form: no entry of its own
    "word": "Tische",
    "pos": "noun",
    "lang_code": "de",
    "senses": [{"glosses": ["plural of Tisch"], "form_of": [{"word": "Tisch"}]}],
}


def write(path: Path, *entries: dict[str, Any]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


def counts(db: Engine) -> tuple[int, int]:
    with db.connect() as conn:
        entries = conn.scalar(select(func.count()).select_from(DictionaryEntry))
        forms = conn.scalar(select(func.count()).select_from(DictionaryForm))
    return entries or 0, forms or 0


def test_examples_and_forms_are_loaded_and_a_second_run_rebuilds_them(
    db: Engine, tmp_path: Path
) -> None:
    path = write(tmp_path / "dump.jsonl", TISCH, GEHEN, FORM_ONLY)

    with db.begin() as conn:
        result = import_file(path, conn)
    assert result["(inflected forms)"] == 3  # tische, tisches, gehst
    assert result["(with an example)"] == 1
    assert counts(db) == (2, 3)  # the form-only line is not an entry

    with db.connect() as conn:
        example = conn.execute(
            select(DictionaryEntry.example_de, DictionaryEntry.example_en).where(
                DictionaryEntry.lemma == "Tisch"
            )
        ).one()
    assert tuple(example) == ("Der Tisch ist gedeckt.", "The table is set.")

    # Importing again changes nothing: forms are replaced, not added twice.
    with db.begin() as conn:
        import_file(path, conn)
    assert counts(db) == (2, 3)

    # A word dropped from the dump takes its forms with it.
    write(path, GEHEN)
    with db.begin() as conn:
        import_file(path, conn)
    assert counts(db) == (1, 1)
