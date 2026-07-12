"""Retired shootout video fields migration.

video_status and video_job_id were TaskIQ-era stored projection columns.
ADR-0007 assigns video state to the video bounded context; fresh baselines do
not create the columns, and the schema-drift cleanup migration removes them
from existing databases.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-09
"""

from collections.abc import Sequence

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: these columns are intentionally absent."""


def downgrade() -> None:
    """No-op: these columns are intentionally absent."""
