"""Drop oauth_tokens table

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-15 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop oauth_tokens table — T3K auth uses API key exchange, not stored OAuth tokens."""
    op.drop_table("oauth_tokens")


def downgrade() -> None:
    """Recreate oauth_tokens table."""
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
    )
