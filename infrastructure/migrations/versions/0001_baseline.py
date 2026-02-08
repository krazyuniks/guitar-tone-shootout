"""Baseline schema — single source of truth for gts_core database.

Creates all 21 tables matching ORM models in webapp.adapters.persistence.models.

New tables: op.create_table('gear_makes'), op.create_table('gear_sources'),
op.create_table('oauth_providers'), op.create_table('user_identities'),
op.create_table('gear_models'), op.create_table('gear_tags'),
op.create_table('audio_segments')

Existing tables modified: block_types, di_tracks, gear, jobs, presets,
shootout_chains, shootouts, signal_chain_blocks, signal_chain_groups,
signal_chains, tags, users

Seed data: oauth_providers (tone3000 provider), block_types

Revision ID: 0001
Revises: (none)
Create Date: 2026-02-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Auth tables ---

    op.create_table(
        "users",
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "oauth_providers",
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=True),
        sa.Column("client_secret", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_oauth_providers"),
        sa.UniqueConstraint("name", name="uq_oauth_providers_name"),
    )

    op.create_table(
        "user_identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_user_identities"),
        sa.ForeignKeyConstraint(["provider_id"], ["oauth_providers.id"], name="fk_user_identities_provider_id_oauth_providers", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_identities_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_user_identities_provider_external", "user_identities", ["provider_id", "external_id"])
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("changes", postgresql.JSON(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    # --- Gear tables ---

    op.create_table(
        "gear_makes",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_gear_makes"),
        sa.UniqueConstraint("name", name="uq_gear_makes_name"),
    )

    op.create_table(
        "gear_sources",
        sa.Column("source_name", sa.String(50), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_gear_sources"),
    )
    op.create_index("ix_gear_sources_source_lookup", "gear_sources", ["source_name", "source_record_id"])

    op.create_table(
        "gear",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(550), nullable=False),
        sa.Column("gear_type", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("make_id", sa.Uuid(), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_gear"),
        sa.ForeignKeyConstraint(["make_id"], ["gear_makes.id"], name="fk_gear_make_id_gear_makes", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], name="fk_gear_source_id_gear_sources", ondelete="SET NULL"),
    )
    op.create_index("ix_gear_type", "gear", ["gear_type"])
    op.create_index("ix_gear_slug", "gear", ["slug"])
    op.create_index("ix_gear_is_public", "gear", ["is_public"])
    op.create_index("ix_gear_make_id", "gear", ["make_id"])
    op.create_index("ix_gear_source_id", "gear", ["source_id"])

    op.create_table(
        "gear_models",
        sa.Column("gear_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("size", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("download_url", sa.String(500), nullable=True),
        sa.Column("download_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_gear_models"),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"], name="fk_gear_models_gear_id_gear", ondelete="CASCADE"),
    )
    op.create_index("ix_gearmodel_gear_id", "gear_models", ["gear_id"])
    op.create_index("ix_gearmodel_platform", "gear_models", ["platform"])

    op.create_table(
        "tags",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    op.create_table(
        "gear_tags",
        sa.Column("gear_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("gear_id", "tag_id", name="pk_gear_tags"),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"], name="fk_gear_tags_gear_id_gear", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_gear_tags_tag_id_tags", ondelete="CASCADE"),
    )

    op.create_table(
        "user_gear",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("gear_id", sa.Uuid(), nullable=True),
        sa.Column("nickname", sa.String(255), nullable=True),
        sa.Column("is_favourite", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_gear"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_gear_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"], name="fk_user_gear_gear_id_gear", ondelete="CASCADE"),
    )
    op.create_index("ix_user_gear_user_id", "user_gear", ["user_id"])
    op.create_index("ix_user_gear_gear_id", "user_gear", ["gear_id"])
    op.create_index("ix_user_gear_is_favourite", "user_gear", ["is_favourite"])

    # --- Signal chain tables ---

    op.create_table(
        "signal_chains",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False, server_default="nam"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_signal_chains"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_signal_chains_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_signal_chains_user_id", "signal_chains", ["user_id"])

    op.create_table(
        "block_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_params", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id", name="pk_block_types"),
        sa.UniqueConstraint("name", name="uq_block_types_name"),
    )

    op.create_table(
        "signal_chain_blocks",
        sa.Column("signal_chain_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("user_gear_id", sa.Uuid(), nullable=True),
        sa.Column("gear_type", sa.String(50), nullable=True),
        sa.Column("block_type_id", sa.Uuid(), nullable=True),
        sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_signal_chain_blocks"),
        sa.ForeignKeyConstraint(["signal_chain_id"], ["signal_chains.id"], name="fk_signal_chain_blocks_signal_chain_id_signal_chains", ondelete="CASCADE"),
    )
    op.create_index("ix_signal_chain_blocks_chain_id", "signal_chain_blocks", ["signal_chain_id"])
    op.create_index("ix_signal_chain_blocks_position", "signal_chain_blocks", ["signal_chain_id", "position"])

    op.create_table(
        "signal_chain_groups",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_chain_id", sa.Uuid(), nullable=True),
        sa.Column("slot_positions", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("gear_options", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("include_null", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_signal_chain_groups"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_signal_chain_groups_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["base_chain_id"], ["signal_chains.id"], name="fk_signal_chain_groups_base_chain_id_signal_chains", ondelete="SET NULL"),
    )
    op.create_index("ix_signal_chain_groups_user_id", "signal_chain_groups", ["user_id"])

    op.create_table(
        "presets",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("signal_chain_block_id", sa.Uuid(), nullable=True),
        sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_presets"),
    )
    op.create_index("ix_presets_block_id", "presets", ["signal_chain_block_id"])

    # --- Shootout tables ---

    op.create_table(
        "di_tracks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("guitar", sa.String(255), nullable=True),
        sa.Column("pickup", sa.String(255), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_di_tracks"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_di_tracks_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_di_tracks_user_id", "di_tracks", ["user_id"])

    op.create_table(
        "shootouts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("di_track_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("video_path", sa.String(500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_shootouts"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_shootouts_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_shootouts_user_id", "shootouts", ["user_id"])
    op.create_index("ix_shootouts_status", "shootouts", ["status"])

    op.create_table(
        "shootout_chains",
        sa.Column("shootout_id", sa.Uuid(), nullable=False),
        sa.Column("signal_chain_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False, server_default=""),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_shootout_chains"),
        sa.ForeignKeyConstraint(["shootout_id"], ["shootouts.id"], name="fk_shootout_chains_shootout_id_shootouts", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_chain_id"], ["signal_chains.id"], name="fk_shootout_chains_signal_chain_id_signal_chains", ondelete="CASCADE"),
    )
    op.create_index("ix_shootout_chains_shootout_id", "shootout_chains", ["shootout_id"])
    op.create_index("ix_shootout_chains_position", "shootout_chains", ["shootout_id", "position"])

    op.create_table(
        "audio_segments",
        sa.Column("shootout_chain_id", sa.Uuid(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("integrated_lufs", sa.Float(), nullable=False),
        sa.Column("peak_dbfs", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audio_segments"),
        sa.ForeignKeyConstraint(["shootout_chain_id"], ["shootout_chains.id"], name="fk_audio_segments_shootout_chain_id_shootout_chains", ondelete="CASCADE"),
    )
    op.create_index("ix_audio_segments_chain_id", "audio_segments", ["shootout_chain_id"])

    # --- Job tables ---

    op.create_table(
        "jobs",
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("parent_job_id", sa.Uuid(), nullable=True),
        sa.Column("depends_on", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_path", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_jobs_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_job_id"], ["jobs.id"], name="fk_jobs_parent_job_id_jobs", ondelete="CASCADE"),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_task_id", "jobs", ["task_id"])
    op.create_index("ix_jobs_entity_id", "jobs", ["entity_id"])


def downgrade() -> None:
    op.drop_table("audio_segments")
    op.drop_table("shootout_chains")
    op.drop_table("shootouts")
    op.drop_table("di_tracks")
    op.drop_table("presets")
    op.drop_table("signal_chain_groups")
    op.drop_table("signal_chain_blocks")
    op.drop_table("block_types")
    op.drop_table("signal_chains")
    op.drop_table("user_gear")
    op.drop_table("gear_tags")
    op.drop_table("tags")
    op.drop_table("gear_models")
    op.drop_table("gear")
    op.drop_table("gear_sources")
    op.drop_table("gear_makes")
    op.drop_table("audit_logs")
    op.drop_table("user_identities")
    op.drop_table("oauth_providers")
    op.drop_table("jobs")
    op.drop_table("users")
