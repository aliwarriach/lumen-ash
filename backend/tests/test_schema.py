from sqlalchemy import Engine, text


def test_every_table_has_row_level_security(db: Engine) -> None:
    """Supabase's Data API is reachable with the app's public key; RLS must block it."""
    with db.connect() as conn:
        unprotected = (
            conn.execute(
                text(
                    "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                    "AND relname <> 'alembic_version' AND NOT c.relrowsecurity"
                )
            )
            .scalars()
            .all()
        )
    assert unprotected == [], f"Enable RLS in the migration for: {unprotected}"
