"""Add source_created_at, downloads_count, favorites_count to gear table.

source_created_at stores when the gear was originally created in the
upstream source (e.g. T3K), separate from created_at which tracks when
the row was inserted into GTS. downloads_count and favorites_count
mirror the upstream source metrics.

Revision ID: 0014
Revises: 0013
Create Date: 2026-02-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add source_created_at, downloads_count, favorites_count columns."""
    op.add_column(
        "gear",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gear",
        sa.Column("downloads_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "gear",
        sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill source_created_at from T3K staging via dblink
    op.execute(
        """
        UPDATE gear g
        SET source_created_at = t.created_at
        FROM gear_sources gs,
             dblink(
                 'dbname=gts_t3k_source user=gts',
                 'SELECT id::text, created_at FROM t3k_tones_staging'
             ) AS t(id text, created_at timestamptz)
        WHERE g.source_id = gs.id
          AND gs.source_record_id = t.id
        """
    )

    # Backfill downloads_count and favorites_count from T3K staging
    op.execute(
        """
        UPDATE gear g
        SET downloads_count = t.downloads_count,
            favorites_count = t.favorites_count
        FROM gear_sources gs,
             dblink(
                 'dbname=gts_t3k_source user=gts',
                 'SELECT id::text, downloads_count, favorites_count FROM t3k_tones_staging'
             ) AS t(id text, downloads_count int, favorites_count int)
        WHERE g.source_id = gs.id
          AND gs.source_record_id = t.id
        """
    )


def downgrade() -> None:
    """Remove source_created_at, downloads_count, favorites_count columns."""
    op.drop_column("gear", "favorites_count")
    op.drop_column("gear", "downloads_count")
    op.drop_column("gear", "source_created_at")
