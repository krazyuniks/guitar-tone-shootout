"""Create T3K staging tables

Revision ID: 0001
Revises:
Create Date: 2026-02-11 02:21:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create T3K staging tables."""
    # Create t3k_creators_staging table
    op.create_table(
        "t3k_creators_staging",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=False),
        sa.Column("profile_url", sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_creators_staging")),
    )

    # Create t3k_packs_staging table
    op.create_table(
        "t3k_packs_staging",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("creator_id", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("pack_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_packs_staging")),
    )

    # Create t3k_models_staging table
    op.create_table(
        "t3k_models_staging",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("pack_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("download_url", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_models_staging")),
    )

    # Create sync_checkpoints table
    op.create_table(
        "sync_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_record_id", sa.String(length=255), nullable=False),
        sa.Column("total_synced", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_checkpoints")),
        sa.UniqueConstraint("source_name", "entity_type", name="uq_source_entity"),
    )


def downgrade() -> None:
    """Drop T3K staging tables."""
    op.drop_table("sync_checkpoints")
    op.drop_table("t3k_models_staging")
    op.drop_table("t3k_packs_staging")
    op.drop_table("t3k_creators_staging")
