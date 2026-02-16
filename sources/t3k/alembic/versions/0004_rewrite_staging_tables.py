"""Rewrite staging tables for T3K API v1

Drop old pack/creator-based staging tables and create new tone/user-based
tables matching the real T3K API response shapes. Data is re-fetchable
from the API so no data migration is needed.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-15 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop old staging tables and create new ones."""
    # Drop old tables
    op.drop_table("t3k_models_staging")
    op.drop_table("t3k_packs_staging")
    op.drop_table("t3k_creators_staging")

    # Reset sync checkpoints (entity types changed)
    op.execute(sa.text("DELETE FROM sync_checkpoints"))

    # Create t3k_users_staging
    op.create_table(
        "t3k_users_staging",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=1024), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_users_staging")),
    )

    # Create t3k_tones_staging
    op.create_table(
        "t3k_tones_staging",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("makes", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("gear", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("models_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloads_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("images", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_tones_staging")),
    )

    # Create t3k_models_staging (new shape)
    op.create_table(
        "t3k_models_staging",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("tone_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model_url", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.String(length=50), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_models_staging")),
    )


def downgrade() -> None:
    """Drop new staging tables and recreate old ones."""
    op.drop_table("t3k_models_staging")
    op.drop_table("t3k_tones_staging")
    op.drop_table("t3k_users_staging")

    # Reset sync checkpoints
    op.execute(sa.text("DELETE FROM sync_checkpoints"))

    # Recreate old tables
    op.create_table(
        "t3k_creators_staging",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=False),
        sa.Column("profile_url", sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_creators_staging")),
    )

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
