"""grammar practice answers count as evidence

Revision ID: 3e9b6c1f0a72
Revises: 8c3f1d2a7e45
Create Date: 2026-11-13 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3e9b6c1f0a72"
down_revision: str | None = "8c3f1d2a7e45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("grammar_evidence", sa.Column("exercise_id", sa.String(length=20), nullable=True))
    op.add_column("grammar_evidence", sa.Column("given", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("grammar_evidence", "given")
    op.drop_column("grammar_evidence", "exercise_id")
