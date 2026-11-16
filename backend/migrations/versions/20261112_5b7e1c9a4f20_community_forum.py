"""community forum

Revision ID: 5b7e1c9a4f20
Revises: d023c6ed0231
Create Date: 2026-11-12 13:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b7e1c9a4f20"
down_revision: str | None = "d023c6ed0231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One counter for the whole chat: a message's place (seq) and its change number (rev).
    op.execute("CREATE SEQUENCE community_change_seq")

    op.create_table(
        "community_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=24), nullable=False),
        sa.Column("name_key", sa.String(length=72), nullable=False),
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_community_profiles")),
        sa.UniqueConstraint("name_key", name=op.f("uq_community_profiles_name_key")),
    )

    op.create_table(
        "community_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "seq",
            sa.BigInteger(),
            server_default=sa.text("nextval('community_change_seq')"),
            nullable=False,
        ),
        sa.Column(
            "rev",
            sa.BigInteger(),
            server_default=sa.text("nextval('community_change_seq')"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reply_to_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reply_to_id"],
            ["community_messages.id"],
            name=op.f("fk_community_messages_reply_to_id_community_messages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_messages")),
        sa.UniqueConstraint("seq", name=op.f("uq_community_messages_seq")),
    )
    op.create_index(op.f("ix_community_messages_rev"), "community_messages", ["rev"], unique=False)
    op.create_index(
        "ix_community_messages_user_id_created_at",
        "community_messages",
        ["user_id", "created_at"],
        unique=False,
    )

    # Block Supabase's public Data API; the backend connects as the table owner. The chat is
    # shared, but only through the backend, which checks the login and the posting limits.
    op.execute("ALTER TABLE community_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE community_messages ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_community_messages_user_id_created_at", table_name="community_messages")
    op.drop_index(op.f("ix_community_messages_rev"), table_name="community_messages")
    op.drop_table("community_messages")
    op.drop_table("community_profiles")
    op.execute("DROP SEQUENCE community_change_seq")
