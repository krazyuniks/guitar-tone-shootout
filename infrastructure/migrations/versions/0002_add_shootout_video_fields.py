"""Add video_status and video_job_id to shootouts table.

Adds two nullable string columns to support video rendering workflow:
- video_status: Current status of video rendering
- video_job_id: Job ID for tracking video rendering task

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add video_status and video_job_id columns to shootouts table."""
    op.add_column(
        "shootouts",
        sa.Column("video_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "shootouts",
        sa.Column("video_job_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    """Remove video_status and video_job_id columns from shootouts table."""
    op.drop_column("shootouts", "video_job_id")
    op.drop_column("shootouts", "video_status")
