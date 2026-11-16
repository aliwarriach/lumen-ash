"""community message attachments (Ask the Community)

Revision ID: c4a8e2f61d93
Revises: b7d2e4a9c1f3
Create Date: 2026-11-15 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a8e2f61d93"
down_revision: str | None = "b7d2e4a9c1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "community_messages",
        sa.Column("attachment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("community_messages", "attachment")
