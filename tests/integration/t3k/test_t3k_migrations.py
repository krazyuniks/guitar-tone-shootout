"""Integration tests for T3K Alembic migrations.

Tests that the T3K source database migrations configuration is correct
and the expected files exist.
"""

from pathlib import Path


class TestT3KAlembicConfiguration:
    """Tests for T3K Alembic configuration."""

    def test_alembic_ini_exists(self) -> None:
        """Test that sources/t3k/alembic.ini exists."""
        t3k_alembic_ini = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic.ini"
        )
        assert t3k_alembic_ini.exists(), "sources/t3k/alembic.ini must exist"

    def test_alembic_env_exists(self) -> None:
        """Test that sources/t3k/alembic/env.py exists."""
        t3k_alembic_env = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic" / "env.py"
        )
        assert t3k_alembic_env.exists(), "sources/t3k/alembic/env.py must exist"

    def test_alembic_versions_directory_exists(self) -> None:
        """Test that sources/t3k/alembic/versions directory exists."""
        versions_dir = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic" / "versions"
        )
        assert versions_dir.exists(), "sources/t3k/alembic/versions directory must exist"
        assert versions_dir.is_dir(), "versions must be a directory"

    def test_initial_migration_exists(self) -> None:
        """Test that initial migration file exists."""
        versions_dir = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic" / "versions"
        )
        migration_files = list(versions_dir.glob("0001_*.py"))
        assert len(migration_files) == 1, "Must have exactly one 0001_*.py migration"

        migration_file = migration_files[0]
        assert "t3k_staging_tables" in migration_file.name.lower()

    def test_alembic_config_points_to_t3k_database(self) -> None:
        """Test that Alembic config references T3K_DATABASE_URL."""
        t3k_alembic_ini = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic.ini"
        )

        content = t3k_alembic_ini.read_text()
        assert "T3K_DATABASE_URL" in content or "gts_t3k_source" in content, (
            "alembic.ini must reference T3K_DATABASE_URL or gts_t3k_source"
        )


class TestT3KDatabaseSeparation:
    """Tests verifying T3K database is separate from gts_core."""

    def test_t3k_env_uses_separate_database_url(self) -> None:
        """Test that T3K env.py references T3K_DATABASE_URL not DATABASE_URL."""
        t3k_env_py = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic" / "env.py"
        )

        content = t3k_env_py.read_text()

        assert "T3K_DATABASE_URL" in content or "gts_t3k_source" in content, (
            "env.py must use T3K-specific database URL"
        )

        assert "webapp.adapters.persistence.models" not in content, (
            "T3K migrations must not import webapp models"
        )

    def test_t3k_models_use_separate_base(self) -> None:
        """Test that T3K models use their own Base, not webapp Base."""
        t3k_models_file = (
            Path(__file__).parent.parent.parent.parent
            / "sources"
            / "t3k"
            / "src"
            / "source_t3k"
            / "adapters"
            / "outbound"
            / "models.py"
        )

        content = t3k_models_file.read_text()

        assert "Base" in content, "models.py must define Base"
        assert "from webapp" not in content, "T3K models must not import from webapp"
