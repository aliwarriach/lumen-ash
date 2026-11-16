"""Checks that a database restored from a backup is one the app can run on.

    python -m app.restore_check RESTORED_URL [--compare SOURCE_URL]

A backup nobody has restored is a hope, not a backup. This is what "it restored" means:
- the migration version is the one this code expects (so the app starts without migrating);
- every table the app uses exists with every column it reads;
- row-level security is on for every table (it keeps Supabase's public Data API out);
- with `--compare`, no table came back smaller than the live database it was dumped from.

Exits 1 and says what is wrong, or 0. The nightly backup workflow runs it on every dump, so a
backup that can't be restored is noticed the next morning instead of the day it is needed.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from app.models import Base

BACKEND = Path(__file__).resolve().parent.parent
# The live database is counted just after the dump, so a big table may have changed a little.
# Small tables get no allowance: a table that comes back with fewer rows than it had is wrong.
SHRINK_TOLERANCE_RATIO = 0.05


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def sync_url(url: str) -> str:
    """Accepts a plain Postgres URL (what Supabase and pg_dump use) or the app's psycopg form."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def expected_head() -> str:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def row_counts(engine: Engine, tables: list[str]) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            t: int(conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar_one()) for t in tables
        }


def check_restored(engine: Engine) -> Report:
    report = Report()
    inspector = inspect(engine)
    present = set(inspector.get_table_names())

    # 1. The migration version
    if "alembic_version" not in present:
        report.problems.append("alembic_version is missing: this is not a restored app database")
    else:
        with engine.connect() as conn:
            versions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        head = expected_head()
        if versions != [head]:
            report.problems.append(
                f"migration version is {versions}, this code expects {head}: "
                "run `alembic upgrade head`, or restore a newer backup"
            )

    # 2. Every table and column the app reads
    expected = [t.name for t in Base.metadata.sorted_tables]
    for table in Base.metadata.sorted_tables:
        if table.name not in present:
            report.problems.append(f"table {table.name} is missing")
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        missing = sorted({c.name for c in table.columns} - have)
        if missing:
            report.problems.append(f"table {table.name} is missing columns: {', '.join(missing)}")

    # 3. Row-level security everywhere
    with engine.connect() as conn:
        open_tables = (
            conn.execute(
                text(
                    "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                    "AND relname <> 'alembic_version' "
                    "AND NOT c.relrowsecurity ORDER BY relname"
                )
            )
            .scalars()
            .all()
        )
    if open_tables:
        report.problems.append(f"row-level security is off for: {', '.join(open_tables)}")

    report.counts = row_counts(engine, [t for t in expected if t in present])
    return report


def compare_counts(restored: dict[str, int], source: dict[str, int]) -> list[str]:
    problems = []
    for table, live in sorted(source.items()):
        back = restored.get(table)
        if back is None:
            continue  # already reported as a missing table
        if live - back > int(live * SHRINK_TOLERANCE_RATIO):
            problems.append(
                f"table {table} came back with {back} rows, the live database has {live}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a database restored from a backup.")
    parser.add_argument("restored_url", help="the database the backup was restored into")
    parser.add_argument("--compare", metavar="SOURCE_URL", help="the live database it came from")
    args = parser.parse_args(argv)

    restored = create_engine(sync_url(args.restored_url))
    report = check_restored(restored)
    if args.compare:
        source = create_engine(sync_url(args.compare))
        tables = list(report.counts)
        report.problems += compare_counts(report.counts, row_counts(source, tables))
        source.dispose()
    restored.dispose()

    width = max((len(t) for t in report.counts), default=0)
    for table, n in report.counts.items():
        print(f"  {table:<{width}}  {n:>9,}")
    if report.ok:
        print(f"OK: at migration {expected_head()}, {len(report.counts)} tables restored.")
        return 0
    print("FAILED:")
    for problem in report.problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
