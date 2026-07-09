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
        "core_gear",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "core_gear",
        sa.Column("downloads_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "core_gear",
        sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill from whichever local T3K staging table exists. This keeps the
    # migration chain runnable in both legacy and consolidated single-DB setups.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.t3k_packs') IS NOT NULL THEN
                UPDATE core_gear g
                SET source_created_at = t.created_at
                FROM core_gear_sources gs, t3k_packs t
                WHERE g.source_id = gs.id
                  AND gs.source_record_id = t.id::text;
            ELSIF to_regclass('public.t3k_tones_staging') IS NOT NULL THEN
                UPDATE core_gear g
                SET source_created_at = t.created_at
                FROM core_gear_sources gs, t3k_tones_staging t
                WHERE g.source_id = gs.id
                  AND gs.source_record_id = t.id::text;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.t3k_packs') IS NOT NULL THEN
                UPDATE core_gear g
                SET downloads_count = t.downloads_count,
                    favorites_count = t.favorites_count
                FROM core_gear_sources gs, t3k_packs t
                WHERE g.source_id = gs.id
                  AND gs.source_record_id = t.id::text;
            ELSIF to_regclass('public.t3k_tones_staging') IS NOT NULL THEN
                UPDATE core_gear g
                SET downloads_count = t.downloads_count,
                    favorites_count = t.favorites_count
                FROM core_gear_sources gs, t3k_tones_staging t
                WHERE g.source_id = gs.id
                  AND gs.source_record_id = t.id::text;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Remove source_created_at, downloads_count, favorites_count columns."""
    op.drop_column("core_gear", "favorites_count")
    op.drop_column("core_gear", "downloads_count")
    op.drop_column("core_gear", "source_created_at")
