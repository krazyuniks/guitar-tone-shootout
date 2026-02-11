"""Create oauth_tokens table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-11 19:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create oauth_tokens table for encrypted T3K API tokens."""
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
    )


def downgrade() -> None:
    """Drop oauth_tokens table."""
    op.drop_table("oauth_tokens")
