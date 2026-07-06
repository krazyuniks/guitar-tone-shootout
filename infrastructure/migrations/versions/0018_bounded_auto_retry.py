"""Bound automatic retry to two attempts total (ADR-0005).

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # max_attempts has no server default (Python-side default only); align the
    # existing rows with the new application default of 2.
    op.execute("UPDATE core_jobs SET max_attempts = 2 WHERE max_attempts = 3")


def downgrade() -> None:
    op.execute("UPDATE core_jobs SET max_attempts = 3 WHERE max_attempts = 2")
