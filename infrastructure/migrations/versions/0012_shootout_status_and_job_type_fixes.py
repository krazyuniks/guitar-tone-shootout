"""Fix ShootoutStatus vocabulary and JobType rename.

- Update shootouts.status: rename 'running' -> 'processing', set server default to 'draft'.
- Update jobs.job_type: rename 'video_composition' -> 'video_compose'.

Revision ID: 0012
Revises: 0011
Create Date: 2026-02-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fix shootout status and job type values."""
    # Rename any stale 'running' shootout statuses to 'processing'
    op.execute("UPDATE core_shootouts SET status = 'processing' WHERE status = 'running'")

    # Update server default for shootouts.status from 'pending' to 'draft'
    op.alter_column("core_shootouts", "status", server_default="draft")

    # Rename 'video_composition' job type to 'video_compose'
    op.execute(
        "UPDATE core_jobs SET job_type = 'video_compose' WHERE job_type = 'video_composition'"
    )


def downgrade() -> None:
    """Revert shootout status and job type fixes."""
    op.execute(
        "UPDATE core_jobs SET job_type = 'video_composition' WHERE job_type = 'video_compose'"
    )
    op.alter_column("core_shootouts", "status", server_default="pending")
    op.execute("UPDATE core_shootouts SET status = 'running' WHERE status = 'processing'")
