"""Add tags table.

Creates the tags table for user-created labels.

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tags table."""
    op.create_table(
        "core_user_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core_users.id"],
            name=op.f("fk_user_tags_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tags")),
        sa.UniqueConstraint("user_id", "name", name=op.f("uq_user_tags_user_id_name")),
    )
    op.create_index(
        op.f("ix_user_tags_user_id"),
        "core_user_tags",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop tags table."""
    op.drop_index(op.f("ix_user_tags_user_id"), table_name="core_user_tags")
    op.drop_table("core_user_tags")
