"""Add channels and waveform columns to di_tracks table.

Adds channels (integer) and waveform (JSON) fields to support audio metadata
extraction and waveform visualization for DI track uploads.

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add channels and waveform columns to di_tracks table."""
    op.add_column(
        "di_tracks",
        sa.Column("channels", sa.Integer(), nullable=True),
    )
    op.add_column(
        "di_tracks",
        sa.Column("waveform", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove channels and waveform columns from di_tracks table."""
    op.drop_column("di_tracks", "waveform")
    op.drop_column("di_tracks", "channels")
