"""Integration test for Alembic migrations."""


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
    assert "target_metadata" in env_content, "Should set target_metadata"

    print("\n✓ Alembic configuration files exist")
    print("✓ env.py imports Base.metadata for autogenerate support")
