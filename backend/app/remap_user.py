"""Gives a restored database to a new login.

    python -m app.remap_user DATABASE_URL OLD_USER_ID NEW_USER_ID

Every row belongs to a Supabase user id, and the backup holds only our own tables, not Supabase's
accounts. If the Supabase project is ever lost and recreated, the learner's new login gets a new
id and a restored database would belong to nobody. This moves everything from the old id to the
new one, in one transaction (all of it or none).

Find OLD_USER_ID in the restored data:  SELECT DISTINCT user_id FROM chapters;
Find NEW_USER_ID in Supabase: Authentication, Users, the learner's row.
"""

import argparse
import sys
from uuid import UUID

from sqlalchemy import Connection, create_engine, text

from app.models import Base
from app.restore_check import sync_url


def user_tables() -> list[str]:
    return [t.name for t in Base.metadata.sorted_tables if "user_id" in t.columns]


def count_rows(conn: Connection, user_id: UUID) -> dict[str, int]:
    return {
        t: int(
            conn.execute(
                text(f'SELECT count(*) FROM "{t}" WHERE user_id = :u'), {"u": user_id}
            ).scalar_one()
        )
        for t in user_tables()
    }


def remap(conn: Connection, old: UUID, new: UUID) -> dict[str, int]:
    """Moves every row of `old` to `new`. Refuses if `new` already has data, so two learners'
    records are never mixed. Returns the rows moved per table."""
    if old == new:
        raise ValueError("The old and new ids are the same.")
    if already := {t: n for t, n in count_rows(conn, new).items() if n}:
        raise ValueError(f"The new user already has data ({', '.join(already)}); refusing to mix.")
    moved = {t: n for t, n in count_rows(conn, old).items() if n}
    if not moved:
        raise ValueError("The old user has no data in this database. Check the id.")
    for table in moved:
        conn.execute(
            text(f'UPDATE "{table}" SET user_id = :new WHERE user_id = :old'),
            {"new": new, "old": old},
        )
    return moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Move restored data to a new Supabase user id.")
    parser.add_argument("database_url")
    parser.add_argument("old_user_id", type=UUID)
    parser.add_argument("new_user_id", type=UUID)
    args = parser.parse_args(argv)

    engine = create_engine(sync_url(args.database_url))
    try:
        with engine.begin() as conn:  # one transaction: all of it or none
            moved = remap(conn, args.old_user_id, args.new_user_id)
    except ValueError as exc:
        print(f"Nothing changed. {exc}")
        return 1
    finally:
        engine.dispose()
    for table, n in moved.items():
        print(f"  {table}: {n} rows")
    print(f"Done: {sum(moved.values())} rows now belong to {args.new_user_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
