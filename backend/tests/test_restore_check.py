import pytest
from sqlalchemy import Engine

from app import restore_check
from app.models import Base


def test_plain_postgres_urls_are_accepted_as_they_come_from_supabase_and_pg_dump() -> None:
    assert (
        restore_check.sync_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    )
    assert restore_check.sync_url("postgres://u@h/db") == "postgresql+psycopg://u@h/db"
    assert restore_check.sync_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"


def test_a_table_that_comes_back_smaller_is_flagged_but_a_whisker_on_a_big_one_is_not() -> None:
    live = {"vocab_words": 2, "dictionary_entries": 84_000, "mistakes": 10, "chapters": 3}
    restored = {"vocab_words": 0, "dictionary_entries": 83_900, "mistakes": 10, "chapters": 2}
    problems = restore_check.compare_counts(restored, live)
    assert [p.split()[1] for p in problems] == ["chapters", "vocab_words"]
    assert "0 rows" in problems[1] and "has 2" in problems[1]


def test_a_restore_with_more_rows_than_the_live_database_is_fine() -> None:
    assert restore_check.compare_counts({"mistakes": 12}, {"mistakes": 10}) == []


def test_a_database_at_the_current_schema_passes(db: Engine) -> None:
    report = restore_check.check_restored(db)
    assert report.ok, report.problems
    assert set(report.counts) == {t.name for t in Base.metadata.sorted_tables}


def test_a_database_at_another_migration_is_refused(
    db: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(restore_check, "expected_head", lambda: "0000000000aa")
    report = restore_check.check_restored(db)
    assert not report.ok
    assert "this code expects 0000000000aa" in report.problems[0]
