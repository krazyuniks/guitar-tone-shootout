"""Add license_text column to gear table.

Adds optional license/terms text field to gear for usage terms.

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add license_text column to gear table."""
    op.add_column(
        "gear",
        sa.Column("license_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove license_text column from gear table."""
    op.drop_column("gear", "license_text")
