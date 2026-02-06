"""Initial schema - transform archive DB to current ORM models.

Baseline: pre-migration-20260202.dump (archive database)
Target: Current ORM models in webapp.adapters.persistence.models

Revision ID: 0001
Revises: (none)
Create Date: 2026-02-06
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Transform archive schema to current ORM schema."""
    conn = op.get_bind()

    # =========================================================================
    # Phase 1: Create NEW tables that don't exist in archive
    # =========================================================================

    # gear_sources (new — replaces gear_source)
    if not _table_exists(conn, "gear_sources"):
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

    # gear_models (new — replaces gear_model)
    if not _table_exists(conn, "gear_models"):
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

    # audio_segments
    if not _table_exists(conn, "audio_segments"):
        op.create_table(
            "audio_segments",
            sa.Column("shootout_chain_id", sa.Uuid(), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("integrated_lufs", sa.Float(), nullable=False),
            sa.Column("peak_dbfs", sa.Float(), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_audio_segments"),
            sa.ForeignKeyConstraint(
                ["shootout_chain_id"], ["shootout_chains.id"],
                name="fk_audio_segments_shootout_chain_id_shootout_chains", ondelete="CASCADE",
            ),
        )
        op.create_index("ix_audio_segments_chain_id", "audio_segments", ["shootout_chain_id"])

    # =========================================================================
    # Phase 2: ALTER existing tables to match ORM
    # =========================================================================

    # --- users ---
    # ORM: id, username, email, avatar_url, is_active, created_at, updated_at
    # Archive: id, tone3000_id, username, avatar_url, access_token, refresh_token, token_expires_at, created_at, updated_at
    if _column_exists(conn, "users", "tone3000_id"):
        op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
        _create_index_safe(conn, "ix_users_email", "users", ["email"])
        # Drop old columns
        op.drop_index("ix_users_tone3000_id", table_name="users")
        op.drop_column("users", "tone3000_id")
        op.drop_column("users", "access_token")
        op.drop_column("users", "refresh_token")
        op.drop_column("users", "token_expires_at")
        # Resize avatar_url
        op.alter_column("users", "avatar_url", type_=sa.String(500), existing_type=sa.String(2000))

    # --- oauth_providers ---
    # ORM: id(UUID), name, client_id, client_secret, enabled
    # Archive: id(INT), name, display_name
    # Recreate with correct schema
    if _column_exists(conn, "oauth_providers", "display_name"):
        # Drop FK from user_identities first
        # Drop ALL FK constraints referencing oauth_providers before dropping the table
        fk_rows = conn.execute(sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE confrelid = 'oauth_providers'::regclass AND contype = 'f'"
        )).fetchall()
        for fk_row in fk_rows:
            fk_name = fk_row[0]
            # Find which table owns this constraint
            owner_table = conn.execute(sa.text(
                "SELECT conrelid::regclass::text FROM pg_constraint WHERE conname = :name"
            ), {"name": fk_name}).scalar()
            op.drop_constraint(fk_name, owner_table, type_="foreignkey")
        op.drop_table("oauth_providers")
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
        # Seed tone3000 provider
        op.bulk_insert(
            sa.table(
                "oauth_providers",
                sa.column("id", sa.Uuid()),
                sa.column("name", sa.String()),
                sa.column("enabled", sa.Boolean()),
            ),
            [{"id": uuid4(), "name": "tone3000", "enabled": True}],
        )

    # --- user_identities ---
    # ORM: id(UUID), user_id, provider_id(UUID), external_id, username, avatar_url(500), created_at, updated_at
    # Archive: id, user_id, provider_id(INT), provider_user_id, email, email_verified, username, avatar_url(2000),
    #          access_token, refresh_token, token_expires_at, created_at, updated_at
    if _column_exists(conn, "user_identities", "provider_user_id"):
        # Get the new provider UUID
        result = conn.execute(sa.text("SELECT id FROM oauth_providers WHERE name='tone3000' LIMIT 1"))
        row = result.fetchone()
        t3k_provider_id = row[0] if row else uuid4()

        # Rebuild user_identities
        op.drop_table("user_identities")
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
            sa.ForeignKeyConstraint(
                ["provider_id"], ["oauth_providers.id"],
                name="fk_user_identities_provider_id_oauth_providers", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_user_identities_user_id_users", ondelete="CASCADE",
            ),
        )
        op.create_index("ix_user_identities_provider_external", "user_identities", ["provider_id", "external_id"])
        op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    # --- gear_makes --- (must be recreated BEFORE gear adds FK to it)
    # ORM: id(UUID), name(100), unique
    # Archive: gear_id, make_id (junction table!)
    if _column_exists(conn, "gear_makes", "gear_id"):
        op.drop_table("gear_makes")
        op.create_table(
            "gear_makes",
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_gear_makes"),
            sa.UniqueConstraint("name", name="uq_gear_makes_name"),
        )

    # --- gear ---
    # ORM: id, name, slug, gear_type(varchar), platform(varchar nullable), description, manufacturer,
    #       make_id, thumbnail_url, is_public, source_id(UUID nullable), created_at, updated_at
    # Archive: id, source_id(INT), source_external_id, name, description, creator, gear_type(ENUM),
    #          platform(ENUM), created_at, updated_at, slug, creator_profile_url, creator_avatar,
    #          license, source_url, image_url, downloads_count, favorites_count, models_count,
    #          is_deleted, source_created_at
    if _column_exists(conn, "gear", "source_external_id"):
        # Add new columns
        op.add_column("gear", sa.Column("manufacturer", sa.String(100), nullable=True))
        op.add_column("gear", sa.Column("make_id", sa.Uuid(), nullable=True))
        op.add_column("gear", sa.Column("thumbnail_url", sa.String(500), nullable=True))
        op.add_column("gear", sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"))

        # Copy image_url to thumbnail_url before dropping
        conn.execute(sa.text("UPDATE gear SET thumbnail_url = image_url WHERE image_url IS NOT NULL"))
        # Copy creator to manufacturer
        conn.execute(sa.text("UPDATE gear SET manufacturer = creator WHERE creator IS NOT NULL"))

        # Drop indexes on enum columns BEFORE altering them
        for idx in ["ix_gear_gear_type", "ix_gear_platform", "ix_gear_type_platform"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="gear")
        # Convert gear_type and platform from ENUM to VARCHAR (raw SQL)
        conn.execute(sa.text("ALTER TABLE gear ALTER COLUMN gear_type TYPE varchar(50) USING gear_type::text"))
        conn.execute(sa.text("ALTER TABLE gear ALTER COLUMN platform TYPE varchar(50) USING platform::text"))
        # Resize name
        op.alter_column("gear", "name", type_=sa.String(255), existing_type=sa.String(500))

        # Change source_id from INT to UUID (nullable)
        op.drop_constraint("fk_gear_source_id_gear_source", "gear", type_="foreignkey")
        op.drop_column("gear", "source_id")
        op.add_column("gear", sa.Column("source_id", sa.Uuid(), nullable=True))
        op.create_foreign_key("fk_gear_source_id_gear_sources", "gear", "gear_sources", ["source_id"], ["id"],
                              ondelete="SET NULL")
        op.create_foreign_key("fk_gear_make_id_gear_makes", "gear", "gear_makes", ["make_id"], ["id"],
                              ondelete="SET NULL")

        # Drop old indexes before dropping columns they reference
        for idx in ["ix_gear_gear_type", "ix_gear_name", "ix_gear_platform", "ix_gear_type_platform",
                     "ix_gear_not_deleted", "ix_gear_downloads"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="gear")

        # Drop old columns
        for col in ["source_external_id", "creator", "creator_profile_url", "creator_avatar",
                     "license", "source_url", "image_url", "downloads_count", "favorites_count",
                     "models_count", "is_deleted", "source_created_at"]:
            if _column_exists(conn, "gear", col):
                op.drop_column("gear", col)
        if _constraint_exists(conn, "gear", "uq_gear_source_external"):
            op.drop_constraint("uq_gear_source_external", "gear", type_="unique")
        _create_index_safe(conn, "ix_gear_type", "gear", ["gear_type"])
        _create_index_safe(conn, "ix_gear_is_public", "gear", ["is_public"])
        _create_index_safe(conn, "ix_gear_make_id", "gear", ["make_id"])
        _create_index_safe(conn, "ix_gear_source_id", "gear", ["source_id"])

    # --- gear_tags ---
    # ORM: gear_id(UUID), tag_id(UUID) — junction, FK to gear + tags
    # Archive: FK to gear + gear_tag (old table). Migrate gear_tag data into tags first.
    if _constraint_exists(conn, "gear_tags", "fk_gear_tags_tag_id_gear_tag"):
        # Copy gear_tag data into tags (include timestamps since NOT NULL)
        conn.execute(sa.text(
            "INSERT INTO tags (id, name, created_at, updated_at) "
            "SELECT id, name, created_at, updated_at FROM gear_tag "
            "ON CONFLICT (id) DO NOTHING"
        ))
        op.drop_constraint("fk_gear_tags_tag_id_gear_tag", "gear_tags", type_="foreignkey")
        op.create_foreign_key("fk_gear_tags_tag_id_tags", "gear_tags", "tags", ["tag_id"], ["id"], ondelete="CASCADE")

    # --- block_types ---
    # ORM: id(UUID), name(100) unique, category(50), description, default_params(JSON)
    # Archive: id(varchar50), name(100), category(30), description, implementation(jsonb), parameters(jsonb),
    #          is_builtin, created_at, updated_at
    if _column_exists(conn, "block_types", "is_builtin"):
        # Truncate and recreate (seed data)
        conn.execute(sa.text("DELETE FROM block_types"))
        op.add_column("block_types", sa.Column("default_params", postgresql.JSON(), nullable=False, server_default="{}"))
        op.alter_column("block_types", "category", type_=sa.String(50), existing_type=sa.String(30))
        op.alter_column("block_types", "id", type_=sa.Uuid(), existing_type=sa.String(50),
                         postgresql_using="gen_random_uuid()")
        if not _constraint_exists(conn, "block_types", "uq_block_types_name"):
            op.create_unique_constraint("uq_block_types_name", "block_types", ["name"])
        for idx in ["ix_block_types_category", "ix_block_types_is_builtin"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="block_types")
        for col in ["is_builtin", "implementation", "parameters", "created_at", "updated_at"]:
            if _column_exists(conn, "block_types", col):
                op.drop_column("block_types", col)
        # Seed block types
        op.bulk_insert(
            sa.table(
                "block_types",
                sa.column("id", sa.Uuid()),
                sa.column("name", sa.String()),
                sa.column("category", sa.String()),
                sa.column("default_params", postgresql.JSON()),
            ),
            [
                {"id": uuid4(), "name": "Gain", "category": "gain", "default_params": {}},
                {"id": uuid4(), "name": "Compressor", "category": "dynamics", "default_params": {}},
                {"id": uuid4(), "name": "EQ", "category": "eq", "default_params": {}},
                {"id": uuid4(), "name": "Chorus", "category": "modulation", "default_params": {}},
                {"id": uuid4(), "name": "Delay", "category": "delay", "default_params": {}},
                {"id": uuid4(), "name": "Reverb", "category": "reverb", "default_params": {}},
            ],
        )

    # --- di_tracks ---
    # ORM: id, user_id, name, file_path(500), original_filename, duration_seconds, sample_rate, description,
    #       guitar, pickup, checksum(nullable), created_at, updated_at
    # Archive: id, uploaded_by, title, description, file_path(1000), file_size_bytes, checksum(NOT NULL),
    #          sample_rate, duration_seconds, waveform_data, guitar, pickups, tuning, strings,
    #          recording_interface, is_system_track, created_at, updated_at, is_public, artist, song
    if _column_exists(conn, "di_tracks", "uploaded_by"):
        op.add_column("di_tracks", sa.Column("user_id", sa.Uuid(), nullable=True))
        op.add_column("di_tracks", sa.Column("name", sa.String(255), nullable=True))
        op.add_column("di_tracks", sa.Column("original_filename", sa.String(255), nullable=True))
        op.add_column("di_tracks", sa.Column("pickup", sa.String(255), nullable=True))
        # Copy data
        conn.execute(sa.text("UPDATE di_tracks SET user_id = uploaded_by, name = title, original_filename = title"))
        # Make NOT NULL after data copy
        op.alter_column("di_tracks", "user_id", nullable=False)
        op.alter_column("di_tracks", "name", nullable=False)
        op.alter_column("di_tracks", "original_filename", nullable=False)
        op.alter_column("di_tracks", "file_path", type_=sa.String(500), existing_type=sa.String(1000))
        op.alter_column("di_tracks", "checksum", nullable=True)
        # Drop old indexes/FKs
        for idx in ["ix_di_tracks_checksum", "ix_di_tracks_created", "ix_di_tracks_is_public", "ix_di_tracks_uploaded_by"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="di_tracks")
        if _constraint_exists(conn, "di_tracks", "fk_di_tracks_uploaded_by_users"):
            op.drop_constraint("fk_di_tracks_uploaded_by_users", "di_tracks", type_="foreignkey")
        op.create_foreign_key("fk_di_tracks_user_id_users", "di_tracks", "users", ["user_id"], ["id"], ondelete="CASCADE")
        _create_index_safe(conn, "ix_di_tracks_user_id", "di_tracks", ["user_id"])
        # Drop old columns
        for col in ["uploaded_by", "title", "file_size_bytes", "is_system_track", "pickups",
                     "is_public", "tuning", "recording_interface", "waveform_data", "strings", "artist", "song"]:
            if _column_exists(conn, "di_tracks", col):
                op.drop_column("di_tracks", col)

    # --- jobs ---
    # ORM: id, user_id, job_type(varchar), parent_job_id, depends_on(JSON), status(varchar), progress,
    #       message, started_at, completed_at, last_heartbeat, attempt, max_attempts, next_retry_at,
    #       result_path, error, task_id, entity_id, created_at, updated_at
    # Archive: id, job_type(ENUM), reference_id, reference_type, user_id, status(ENUM), progress, message,
    #          error_message, retry_count, started_at, completed_at, created_at, updated_at,
    #          last_heartbeat, next_retry_at, task_id, parent_job_id, result_path, config
    if _column_exists(conn, "jobs", "retry_count"):
        op.add_column("jobs", sa.Column("depends_on", postgresql.JSON(), nullable=False, server_default="[]"))
        op.add_column("jobs", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        op.add_column("jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
        op.add_column("jobs", sa.Column("error", sa.Text(), nullable=True))
        op.add_column("jobs", sa.Column("entity_id", sa.Uuid(), nullable=True))
        # Copy error_message to error
        conn.execute(sa.text("UPDATE jobs SET error = error_message WHERE error_message IS NOT NULL"))
        conn.execute(sa.text("UPDATE jobs SET attempt = retry_count + 1 WHERE retry_count > 0"))
        # Drop indexes that reference enum types BEFORE altering columns
        for idx in ["ix_jobs_job_type", "ix_jobs_reference", "ix_jobs_status",
                     "ix_jobs_unique_active_shootout", "ix_jobs_unique_active_t3k_sync"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="jobs")
        # Convert enums to varchar (raw SQL — Alembic can't handle enum→varchar)
        conn.execute(sa.text("ALTER TABLE jobs ALTER COLUMN job_type TYPE varchar(50) USING job_type::text"))
        conn.execute(sa.text("ALTER TABLE jobs ALTER COLUMN status TYPE varchar(50) USING status::text"))
        _create_index_safe(conn, "ix_jobs_entity_id", "jobs", ["entity_id"])
        _create_index_safe(conn, "ix_jobs_status", "jobs", ["status"])
        _create_index_safe(conn, "ix_jobs_task_id", "jobs", ["task_id"])
        # Drop old columns
        for col in ["retry_count", "reference_id", "reference_type", "config", "error_message"]:
            if _column_exists(conn, "jobs", col):
                op.drop_column("jobs", col)

    # --- presets ---
    # ORM: id, signal_chain_block_id, name(100), params(JSON)
    # Archive: id, user_id, name(255), description, signal_chain(jsonb), tags, category, genre,
    #          is_public, is_factory, version, created_at, updated_at
    if _column_exists(conn, "presets", "is_factory"):
        conn.execute(sa.text("DELETE FROM presets"))  # Can't migrate structure, clear
        op.add_column("presets", sa.Column("signal_chain_block_id", sa.Uuid(), nullable=True))
        op.add_column("presets", sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"))
        op.alter_column("presets", "name", type_=sa.String(100), existing_type=sa.String(255))
        # Drop old indexes
        for idx in ["ix_presets_category", "ix_presets_is_factory", "ix_presets_is_public",
                     "ix_presets_user_created", "ix_presets_user_id"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="presets")
        if _constraint_exists(conn, "presets", "fk_presets_user_id_users"):
            op.drop_constraint("fk_presets_user_id_users", "presets", type_="foreignkey")
        _create_index_safe(conn, "ix_presets_block_id", "presets", ["signal_chain_block_id"])
        # Drop old columns
        for col in ["user_id", "description", "signal_chain", "tags", "created_at",
                     "is_public", "version", "genre", "is_factory", "updated_at", "category"]:
            if _column_exists(conn, "presets", col):
                op.drop_column("presets", col)

    # --- signal_chains ---
    # ORM: id, user_id, name, description, platform(varchar), created_at, updated_at
    # Archive: + is_valid, is_complete, group_id
    if _column_exists(conn, "signal_chains", "is_valid"):
        op.alter_column("signal_chains", "platform", type_=sa.String(50), existing_type=sa.String(20))
        if _index_exists(conn, "ix_signal_chains_group_id"):
            op.drop_index("ix_signal_chains_group_id", table_name="signal_chains")
        if _index_exists(conn, "ix_signal_chains_user_created"):
            op.drop_index("ix_signal_chains_user_created", table_name="signal_chains")
        if _constraint_exists(conn, "signal_chains", "fk_signal_chains_group_id_signal_chain_groups"):
            op.drop_constraint("fk_signal_chains_group_id_signal_chain_groups", "signal_chains", type_="foreignkey")
        for col in ["is_valid", "is_complete", "group_id"]:
            if _column_exists(conn, "signal_chains", col):
                op.drop_column("signal_chains", col)

    # --- signal_chain_blocks ---
    # ORM: id, signal_chain_id, position, user_gear_id(nullable), gear_type(varchar nullable),
    #       block_type_id(nullable), params(JSON)
    # Archive: id, chain_id, position, user_gear_id, created_at, updated_at
    if _column_exists(conn, "signal_chain_blocks", "chain_id"):
        op.add_column("signal_chain_blocks", sa.Column("signal_chain_id", sa.Uuid(), nullable=True))
        op.add_column("signal_chain_blocks", sa.Column("gear_type", sa.String(50), nullable=True))
        op.add_column("signal_chain_blocks", sa.Column("block_type_id", sa.Uuid(), nullable=True))
        op.add_column("signal_chain_blocks", sa.Column("params", postgresql.JSON(), nullable=False, server_default="{}"))
        conn.execute(sa.text("UPDATE signal_chain_blocks SET signal_chain_id = chain_id"))
        op.alter_column("signal_chain_blocks", "signal_chain_id", nullable=False)
        op.alter_column("signal_chain_blocks", "user_gear_id", nullable=True)
        # Drop old indexes/FKs
        for idx in ["ix_signal_chain_blocks_user_gear_id", "uq_signal_chain_blocks_chain_position",
                     "ix_signal_chain_blocks_chain_id"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="signal_chain_blocks")
        if _constraint_exists(conn, "signal_chain_blocks", "fk_signal_chain_blocks_chain_id_signal_chains"):
            op.drop_constraint("fk_signal_chain_blocks_chain_id_signal_chains", "signal_chain_blocks", type_="foreignkey")
        if _constraint_exists(conn, "signal_chain_blocks", "fk_signal_chain_blocks_user_gear_id_user_gear"):
            op.drop_constraint("fk_signal_chain_blocks_user_gear_id_user_gear", "signal_chain_blocks", type_="foreignkey")
        op.create_foreign_key(
            "fk_signal_chain_blocks_signal_chain_id_signal_chains",
            "signal_chain_blocks", "signal_chains", ["signal_chain_id"], ["id"], ondelete="CASCADE",
        )
        _create_index_safe(conn, "ix_signal_chain_blocks_chain_id", "signal_chain_blocks", ["signal_chain_id"])
        _create_index_safe(conn, "ix_signal_chain_blocks_position", "signal_chain_blocks", ["signal_chain_id", "position"])
        for col in ["created_at", "updated_at", "chain_id"]:
            if _column_exists(conn, "signal_chain_blocks", col):
                op.drop_column("signal_chain_blocks", col)

    # --- signal_chain_groups ---
    # ORM: id, user_id, name, description, base_chain_id, slot_positions(JSON), gear_options(JSON),
    #       include_null, created_at, updated_at
    # Archive: id, user_id, name, platform, created_at, updated_at
    if _column_exists(conn, "signal_chain_groups", "platform"):
        op.add_column("signal_chain_groups", sa.Column("description", sa.Text(), nullable=True))
        op.add_column("signal_chain_groups", sa.Column("base_chain_id", sa.Uuid(), nullable=True))
        op.add_column("signal_chain_groups", sa.Column("slot_positions", postgresql.JSON(), nullable=False, server_default="[]"))
        op.add_column("signal_chain_groups", sa.Column("gear_options", postgresql.JSON(), nullable=False, server_default="{}"))
        op.add_column("signal_chain_groups", sa.Column("include_null", sa.Boolean(), nullable=False, server_default="false"))
        op.create_foreign_key(
            "fk_signal_chain_groups_base_chain_id_signal_chains",
            "signal_chain_groups", "signal_chains", ["base_chain_id"], ["id"], ondelete="SET NULL",
        )
        if _index_exists(conn, "ix_signal_chain_groups_user_created"):
            op.drop_index("ix_signal_chain_groups_user_created", table_name="signal_chain_groups")
        op.drop_column("signal_chain_groups", "platform")

    # --- shootouts ---
    # ORM: id, user_id, di_track_id(nullable), name, description, status(varchar), video_path,
    #       created_at, updated_at
    # Archive: id, user_id, name, description, status(varchar20), output_path, error_message,
    #          output_format, sample_rate, created_at, updated_at, master_audio_path, group_id
    if _column_exists(conn, "shootouts", "group_id"):
        op.add_column("shootouts", sa.Column("di_track_id", sa.Uuid(), nullable=True))
        op.add_column("shootouts", sa.Column("video_path", sa.String(500), nullable=True))
        op.alter_column("shootouts", "status", type_=sa.String(50), existing_type=sa.String(20))
        if _constraint_exists(conn, "shootouts", "fk_shootouts_group_id"):
            op.drop_constraint("fk_shootouts_group_id", "shootouts", type_="foreignkey")
        for idx in ["ix_shootouts_group_id", "ix_shootouts_user_created"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="shootouts")
        _create_index_safe(conn, "ix_shootouts_status", "shootouts", ["status"])
        for col in ["master_audio_path", "group_id", "sample_rate", "output_format", "output_path", "error_message"]:
            if _column_exists(conn, "shootouts", col):
                op.drop_column("shootouts", col)

    # --- shootout_chains ---
    # ORM: id, shootout_id, signal_chain_id, position, label
    # Archive: id, shootout_id, chain_id, position, audio_path, metrics_json, ai_eval_json,
    #          created_at, updated_at, duration_ms, di_track_id
    if _column_exists(conn, "shootout_chains", "chain_id"):
        op.add_column("shootout_chains", sa.Column("signal_chain_id", sa.Uuid(), nullable=True))
        op.add_column("shootout_chains", sa.Column("label", sa.String(100), nullable=False, server_default=""))
        conn.execute(sa.text("UPDATE shootout_chains SET signal_chain_id = chain_id"))
        op.alter_column("shootout_chains", "signal_chain_id", nullable=False)
        for idx in ["ix_shootout_chains_chain_id", "ix_shootout_chains_di_track_id",
                     "uq_shootout_chains_di_chain", "uq_shootout_chains_position"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="shootout_chains")
        if _constraint_exists(conn, "shootout_chains", "fk_shootout_chains_chain_id_signal_chains"):
            op.drop_constraint("fk_shootout_chains_chain_id_signal_chains", "shootout_chains", type_="foreignkey")
        if _constraint_exists(conn, "shootout_chains", "fk_shootout_chains_di_track_id"):
            op.drop_constraint("fk_shootout_chains_di_track_id", "shootout_chains", type_="foreignkey")
        op.create_foreign_key(
            "fk_shootout_chains_signal_chain_id_signal_chains",
            "shootout_chains", "signal_chains", ["signal_chain_id"], ["id"], ondelete="CASCADE",
        )
        _create_index_safe(conn, "ix_shootout_chains_position", "shootout_chains", ["shootout_id", "position"])
        for col in ["duration_ms", "ai_eval_json", "metrics_json", "di_track_id", "created_at", "chain_id", "updated_at", "audio_path"]:
            if _column_exists(conn, "shootout_chains", col):
                op.drop_column("shootout_chains", col)

    # --- tags ---
    # ORM: id, name unique
    # Archive: id, name(100), created_at, updated_at
    # Keep name at varchar(100) — data has names up to 62 chars
    if _column_exists(conn, "tags", "created_at"):
        if _index_exists(conn, "ix_tags_name"):
            op.drop_index("ix_tags_name", table_name="tags")
        if not _constraint_exists(conn, "tags", "uq_tags_name"):
            op.create_unique_constraint("uq_tags_name", "tags", ["name"])
        for col in ["created_at", "updated_at"]:
            if _column_exists(conn, "tags", col):
                op.drop_column("tags", col)

    # --- user_gear ---
    # ORM: id, user_id, gear_id, nickname, notes, is_favourite, created_at, updated_at
    #       + unique(user_id, gear_id)
    # Archive: id, user_id, display_name, is_favorite, notes, created_at, updated_at, gear_model_id
    if _column_exists(conn, "user_gear", "gear_model_id"):
        op.add_column("user_gear", sa.Column("gear_id", sa.Uuid(), nullable=True))
        # Rename display_name -> nickname
        op.alter_column("user_gear", "display_name", new_column_name="nickname")
        # Rename is_favorite -> is_favourite
        op.alter_column("user_gear", "is_favorite", new_column_name="is_favourite")
        # Drop old FK/indexes
        if _constraint_exists(conn, "user_gear", "fk_user_gear_gear_model_id"):
            op.drop_constraint("fk_user_gear_gear_model_id", "user_gear", type_="foreignkey")
        for idx in ["ix_user_gear_favorites", "ix_user_gear_gear_model_id"]:
            if _index_exists(conn, idx):
                op.drop_index(idx, table_name="user_gear")
        op.drop_column("user_gear", "gear_model_id")
        op.create_foreign_key("fk_user_gear_gear_id_gear", "user_gear", "gear", ["gear_id"], ["id"], ondelete="CASCADE")
        _create_index_safe(conn, "ix_user_gear_gear_id", "user_gear", ["gear_id"])
        _create_index_safe(conn, "ix_user_gear_is_favourite", "user_gear", ["is_favourite"])

    # =========================================================================
    # Phase 3: Drop legacy tables (in dependency order)
    # =========================================================================
    legacy_tables = [
        # Drop junction/child tables first
        "di_track_tags", "user_gear_tags", "user_notifications", "error_reports",
        "t3k_pack_tags", "t3k_pack_makes", "t3k_pack_images", "t3k_pack_links",
        "t3k_models", "signal_chain_group_amps", "signal_chain_group_dis", "signal_chain_group_irs",
        # Then parent tables
        "t3k_packs", "t3k_creators", "t3k_makes", "t3k_tags",
        # Old versions of renamed tables
        "gear_model", "gear_source", "gear_make", "gear_tag", "gear_link",
    ]
    for table in legacy_tables:
        if _table_exists(conn, table):
            conn.execute(sa.text(f'DROP TABLE "{table}" CASCADE'))

    # Drop orphaned enum types
    for enum_name in ["gear_type", "gear_platform", "gear_license", "job_type", "job_status",
                      "t3k_gear_type", "t3k_platform", "t3k_license", "t3k_link_type",
                      "t3k_model_size", "t3k_pack_sync_status", "download_status"]:
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))


def downgrade() -> None:
    """Not supported — this is the initial schema."""
    raise NotImplementedError("Cannot downgrade past initial schema")


# =============================================================================
# Helper functions for idempotent operations
# =============================================================================

def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:name)"
    ), {"name": table_name})
    return result.scalar()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=:table AND column_name=:col)"
    ), {"table": table_name, "col": column_name})
    return result.scalar()


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname=:name)"
    ), {"name": index_name})
    return result.scalar()


def _create_index_safe(conn, index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    """Create index only if it doesn't already exist."""
    if not _index_exists(conn, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def _constraint_exists(conn, table_name: str, constraint_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_name=:table AND constraint_name=:name)"
    ), {"table": table_name, "name": constraint_name})
    return result.scalar()
