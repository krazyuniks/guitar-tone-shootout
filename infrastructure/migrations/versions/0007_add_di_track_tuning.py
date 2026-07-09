"""Add tuning column to di_tracks table.

Adds an optional tuning field to track the guitar tuning used for DI recordings.
This supports the frontend form field that was previously unmapped.

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add tuning column to di_tracks table."""
    op.add_column(
        "core_di_tracks",
        sa.Column("tuning", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    """Remove tuning column from di_tracks table."""
    op.drop_column("core_di_tracks", "tuning")
