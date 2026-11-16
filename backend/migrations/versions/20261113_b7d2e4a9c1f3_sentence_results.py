"""sentence lesson results

Revision ID: b7d2e4a9c1f3
Revises: 3e9b6c1f0a72
Create Date: 2026-11-13 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2e4a9c1f3"
down_revision: str | None = "3e9b6c1f0a72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sentence_results",
        sa.Column("lesson_id", sa.String(length=30), nullable=False),
        sa.Column("best_right", sa.Integer(), nullable=False),
        sa.Column("last_right", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sentence_results")),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_sentence_results_lesson"),
    )
    op.create_index(
        op.f("ix_sentence_results_user_id"), "sentence_results", ["user_id"], unique=False
    )
    op.execute("ALTER TABLE sentence_results ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f("ix_sentence_results_user_id"), table_name="sentence_results")
    op.drop_table("sentence_results")
