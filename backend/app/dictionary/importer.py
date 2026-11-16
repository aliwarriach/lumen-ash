"""Loads the kaikki.org German Wiktionary dump into `dictionary_entries` (and the inflected forms
into `dictionary_forms`, so "gehst" finds gehen).

A one-off command, run from a developer machine (not a background worker):

    curl -LO https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl
    uv run python -m app.dictionary.importer kaikki.org-dictionary-German.jsonl

It runs in one transaction: if anything fails, the existing dictionary is left untouched.
Re-running updates entries in place and removes ones no longer in the dump.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, create_engine, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.dictionary.models import DictionaryEntry, DictionaryForm
from app.dictionary.parser import ParsedEntry, parse_entry

BATCH_SIZE = 2000
FORM_BATCH_SIZE = 10_000


def _row(entry: ParsedEntry, source_key: str) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "lemma": entry.lemma,
        "lemma_lower": entry.lemma.lower(),
        "pos": entry.pos,
        "genders": entry.genders,
        "plurals": entry.plurals,
        "plural_only": entry.plural_only,
        "meanings": entry.meanings,
        "ipa": entry.ipa,
        "audio_url": entry.audio_url,
        "verb_forms": entry.verb_forms,
        "example_de": entry.example_de,
        "example_en": entry.example_en,
    }


def _upsert(conn: Connection, rows: list[dict[str, Any]]) -> None:
    stmt = insert(DictionaryEntry).values(rows)
    updated = {c: stmt.excluded[c] for c in rows[0] if c != "source_key"}
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[DictionaryEntry.source_key],
            set_={**updated, "imported_at": func.now()},
        )
    )


def _replace_forms(conn: Connection, forms_by_key: dict[str, list[str]]) -> int:
    """Rebuilds `dictionary_forms` from scratch: entry ids are looked up by source key."""
    ids = {
        source_key: entry_id
        for source_key, entry_id in conn.execute(
            select(DictionaryEntry.source_key, DictionaryEntry.id)
        )
    }
    conn.execute(delete(DictionaryForm))
    rows: list[dict[str, Any]] = []
    total = 0
    for source_key, forms in forms_by_key.items():
        entry_id = ids.get(source_key)
        if entry_id is None:
            continue
        for form in {f.lower() for f in forms}:
            rows.append({"form_lower": form, "entry_id": entry_id})
            if len(rows) >= FORM_BATCH_SIZE:
                conn.execute(insert(DictionaryForm), rows)
                total += len(rows)
                rows.clear()
    if rows:
        conn.execute(insert(DictionaryForm), rows)
        total += len(rows)
    return total


def import_file(path: Path, conn: Connection) -> Counter[str]:
    occurrences: Counter[tuple[str, str, int]] = Counter()
    kept: Counter[str] = Counter()
    batch: list[dict[str, Any]] = []
    forms_by_key: dict[str, list[str]] = {}

    with path.open(encoding="utf-8") as lines:
        for line in lines:
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry = parse_entry(raw)
            if entry is None:
                continue
            identity = (entry.lemma, entry.pos, entry.etymology)
            occurrences[identity] += 1
            source_key = f"{entry.lemma}|{entry.pos}|{entry.etymology}|{occurrences[identity]}"
            if len(source_key) > 300:
                continue
            batch.append(_row(entry, source_key))
            if entry.forms:
                forms_by_key[source_key] = entry.forms
            kept[entry.pos] += 1
            if len(batch) >= BATCH_SIZE:
                _upsert(conn, batch)
                batch.clear()
    if batch:
        _upsert(conn, batch)

    # now() is fixed for the whole transaction, so every row touched above has this timestamp.
    stale = conn.execute(
        delete(DictionaryEntry).where(
            DictionaryEntry.imported_at < select(func.now()).scalar_subquery()
        )
    )
    kept["(removed stale)"] = stale.rowcount
    kept["(inflected forms)"] = _replace_forms(conn, forms_by_key)
    kept["(with an example)"] = (
        conn.scalar(
            select(func.count())
            .select_from(DictionaryEntry)
            .where(DictionaryEntry.example_de.is_not(None))
        )
        or 0
    )
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("path", type=Path, help="kaikki.org German .jsonl file")
    args = parser.parse_args()
    if not args.path.is_file():
        sys.exit(f"Not a file: {args.path}")

    engine = create_engine(get_settings().database_url)
    started = time.monotonic()
    with engine.begin() as conn:
        counts = import_file(args.path, conn)
    # Updating every row leaves the old versions behind. VACUUM marks that space reusable, so
    # repeated imports level off at about twice the data size (~75 MB) instead of growing.
    # VACUUM can't run inside a transaction.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM ANALYZE dictionary_entries"))
        conn.execute(text("VACUUM ANALYZE dictionary_forms"))
    total = sum(v for k, v in counts.items() if not k.startswith("("))
    print(f"Imported {total} entries in {time.monotonic() - started:.0f}s")
    for name, n in counts.most_common():
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
