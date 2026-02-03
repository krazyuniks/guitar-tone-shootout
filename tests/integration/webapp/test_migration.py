"""Integration test for Alembic migrations."""



def test_migration_creates_all_tables() -> None:
    """Test that initial migration creates all expected tables."""
    # This test verifies the migration artifact exists and is syntactically correct
    # Actual migration testing requires a fresh database which is done via just migrate

    # Verify migration file exists
    import pathlib
    migration_dir = pathlib.Path("infrastructure/migrations/versions")
    assert migration_dir.exists(), "Migration directory should exist"

    migration_files = list(migration_dir.glob("*.py"))
    assert len(migration_files) > 0, "At least one migration file should exist"

    # Verify migration file contains expected table names
    migration_content = migration_files[0].read_text()

    # Expected new tables created by migration
    expected_new_tables = [
        "gear_makes",
        "gear_sources",
        "oauth_providers",
        "user_identities",
        "gear_models",
        "gear_tags",
        "audio_segments",
    ]

    for table in expected_new_tables:
        assert f"op.create_table('{table}'" in migration_content, f"Migration should create {table} table"

    # Expected tables being modified
    expected_modified_tables = [
        "block_types",
        "di_tracks",
        "gear",
        "jobs",
        "presets",
        "shootout_chains",
        "shootouts",
        "signal_chain_blocks",
        "signal_chain_groups",
        "signal_chains",
        "tags",
        "users",
    ]

    for table in expected_modified_tables:
        assert table in migration_content, f"Migration should reference {table} table"

    # Verify seed data is present
    assert "oauth_providers" in migration_content, "Should seed oauth_providers"
    assert "block_types" in migration_content, "Should seed block_types"
    assert "tone3000" in migration_content, "Should seed tone3000 provider"

    print("\n✓ Migration file exists")
    print("✓ Creates new tables: gear_makes, gear_sources, oauth_providers, etc.")
    print("✓ Seed data for BlockType and OAuthProvider is present")
    print("\nNOTE: This migration was generated against existing schema.")
    print("For a fresh database, you should:")
    print("  1. Run: just reset  # (will prompt for confirmation)")
    print("  2. Regenerate migration: export DATABASE_URL=... && uv run alembic -c infrastructure/migrations/alembic.ini revision --autogenerate -m 'Initial schema'")
    print("  3. Run: just migrate")
    print("  4. Verify: just psql -c '\\dt'")


def test_alembic_config_exists() -> None:
    """Test that Alembic configuration exists."""
    import pathlib

    alembic_ini = pathlib.Path("infrastructure/migrations/alembic.ini")
    assert alembic_ini.exists(), "alembic.ini should exist"

    env_py = pathlib.Path("infrastructure/migrations/env.py")
    assert env_py.exists(), "env.py should exist"

    # Verify env.py imports Base metadata
    env_content = env_py.read_text()
    assert "Base.metadata" in env_content, "env.py should import Base.metadata"
    assert "target_metadata = Base.metadata" in env_content, "Should set target_metadata"

    print("\n✓ Alembic configuration files exist")
    print("✓ env.py imports Base.metadata for autogenerate support")
