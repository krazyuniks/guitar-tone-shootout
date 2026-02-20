"""Merge T3K tables into core database with bounded-context prefixes.

Revision ID: 0015
Revises: 0014
Create Date: 2026-02-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in set(inspector.get_table_names())


def upgrade() -> None:
    """Create T3K-prefixed tables in gts_core and ensure pgmq is installed."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_partman")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgmq")

    if not _table_exists("t3k_creators"):
        op.create_table(
            "t3k_creators",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("avatar_url", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("bio", sa.Text(), nullable=False, server_default=""),
            sa.Column("url", sa.String(length=1024), nullable=False, server_default=""),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_creators")),
        )

    if not _table_exists("t3k_packs"):
        op.create_table(
            "t3k_packs",
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
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_packs")),
        )

    if not _table_exists("t3k_models"):
        op.create_table(
            "t3k_models",
            sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("tone_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("model_url", sa.String(length=1024), nullable=False),
            sa.Column("size", sa.String(length=50), nullable=False, server_default="standard"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("file_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_models")),
        )

    if not _table_exists("t3k_sync_checkpoints"):
        op.create_table(
            "t3k_sync_checkpoints",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("source_name", sa.String(length=50), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_record_id", sa.String(length=255), nullable=False),
            sa.Column("total_synced", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_sync_checkpoints")),
            sa.UniqueConstraint(
                "source_name",
                "entity_type",
                name="uq_t3k_sync_checkpoints_source_entity",
            ),
        )

    if not _table_exists("t3k_tags"):
        op.create_table(
            "t3k_tags",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.ForeignKeyConstraint(["pack_id"], ["t3k_packs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_tags")),
            sa.UniqueConstraint("pack_id", "name", name="uq_t3k_tags_pack_name"),
        )

    if not _table_exists("t3k_makes"):
        op.create_table(
            "t3k_makes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.ForeignKeyConstraint(["pack_id"], ["t3k_packs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_makes")),
            sa.UniqueConstraint("pack_id", "name", name="uq_t3k_makes_pack_name"),
        )

    if not _table_exists("t3k_pack_images"):
        op.create_table(
            "t3k_pack_images",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("url", sa.String(length=1024), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["pack_id"], ["t3k_packs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_pack_images")),
            sa.UniqueConstraint("pack_id", "url", name="uq_t3k_pack_images_pack_url"),
        )

    if not _table_exists("t3k_pack_links"):
        op.create_table(
            "t3k_pack_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("url", sa.String(length=1024), nullable=False),
            sa.Column("link_type", sa.String(length=50), nullable=False, server_default="tone"),
            sa.ForeignKeyConstraint(["pack_id"], ["t3k_packs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_t3k_pack_links")),
            sa.UniqueConstraint("pack_id", "url", name="uq_t3k_pack_links_pack_url"),
        )


def downgrade() -> None:
    """Drop T3K-prefixed tables from gts_core."""
    op.execute("DROP TABLE IF EXISTS t3k_pack_links CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_pack_images CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_makes CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_sync_checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_models CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_packs CASCADE")
    op.execute("DROP TABLE IF EXISTS t3k_creators CASCADE")
