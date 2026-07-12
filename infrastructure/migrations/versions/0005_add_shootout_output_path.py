"""Add output_path to shootouts table.

Adds nullable string column to store the path to the master audio file
created after processing all shootout chains.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add output_path column to shootouts table."""
    op.add_column(
        "core_shootouts",
        sa.Column("output_path", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    """Remove output_path column from shootouts table."""
    op.drop_column("core_shootouts", "output_path")
