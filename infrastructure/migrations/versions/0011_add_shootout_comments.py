"""Add shootout_comments table.

Creates the shootout_comments table for user comments on shootouts.

Revision ID: 0011
Revises: 0010
Create Date: 2026-02-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shootout_comments table."""
    op.create_table(
        "core_shootout_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("shootout_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["shootout_id"],
            ["core_shootouts.id"],
            name=op.f("fk_shootout_comments_shootout_id_shootouts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core_users.id"],
            name=op.f("fk_shootout_comments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shootout_comments")),
    )
    op.create_index(
        op.f("ix_shootout_comments_shootout_id"),
        "core_shootout_comments",
        ["shootout_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_shootout_comments_user_id"),
        "core_shootout_comments",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop shootout_comments table."""
    op.drop_index(op.f("ix_shootout_comments_user_id"), table_name="core_shootout_comments")
    op.drop_index(op.f("ix_shootout_comments_shootout_id"), table_name="core_shootout_comments")
    op.drop_table("core_shootout_comments")
