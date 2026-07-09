"""Add waveform column to audio_segments table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable waveform JSON column to audio_segments."""
    op.add_column(
        "core_audio_segments",
        sa.Column("waveform", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove waveform column from audio_segments."""
    op.drop_column("core_audio_segments", "waveform")
