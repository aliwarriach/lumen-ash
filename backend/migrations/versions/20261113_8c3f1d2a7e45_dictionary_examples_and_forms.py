"""dictionary example sentences and inflected forms

Revision ID: 8c3f1d2a7e45
Revises: 5b7e1c9a4f20
Create Date: 2026-11-13 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c3f1d2a7e45"
down_revision: str | None = "5b7e1c9a4f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dictionary_entries", sa.Column("example_de", sa.Text(), nullable=True))
    op.add_column("dictionary_entries", sa.Column("example_en", sa.Text(), nullable=True))

    op.create_table(
        "dictionary_forms",
        sa.Column("form_lower", sa.String(length=60), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["dictionary_entries.id"],
            name=op.f("fk_dictionary_forms_entry_id_dictionary_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("form_lower", "entry_id", name=op.f("pk_dictionary_forms")),
    )
    # Reference data shared by every learner, like dictionary_entries: readable by the backend
    # only. Same row-level-security stance as the other shared tables (see the first migration).
    op.execute("ALTER TABLE dictionary_forms ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("dictionary_forms")
    op.drop_column("dictionary_entries", "example_en")
    op.drop_column("dictionary_entries", "example_de")
