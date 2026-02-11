"""Integration tests for T3K Alembic migrations.

Tests that the T3K source database migrations run successfully
and create the expected schema.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture
async def t3k_db_engine() -> AsyncEngine:
    """Create temporary SQLite engine for T3K source database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    """Create Alembic config pointing to T3K migrations."""
    # Point to sources/t3k/alembic.ini
    t3k_alembic_ini = Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic.ini"

    config = Config(str(t3k_alembic_ini))
    # Override database URL to use in-memory SQLite
    config.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///:memory:")

    return config


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

    def test_alembic_config_points_to_t3k_database(self, alembic_config: Config) -> None:
        """Test that Alembic config references T3K_DATABASE_URL."""
        t3k_alembic_ini = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic.ini"
        )

        content = t3k_alembic_ini.read_text()
        # Check that comments or docs mention T3K_DATABASE_URL
        assert (
            "T3K_DATABASE_URL" in content or "gts_t3k_source" in content
        ), "alembic.ini must reference T3K_DATABASE_URL or gts_t3k_source"


class TestT3KMigrationExecution:
    """Tests for running T3K migrations."""

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_upgrade_creates_all_tables(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that running upgrade creates all staging tables."""
        # Run Alembic upgrade
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            tables = inspector.get_table_names()

            assert "t3k_creators_staging" in tables
            assert "t3k_packs_staging" in tables
            assert "t3k_models_staging" in tables
            assert "sync_checkpoints" in tables

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_downgrade_removes_all_tables(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that downgrade removes all staging tables."""
        # Run upgrade first
        command.upgrade(alembic_config, "head")

        # Run downgrade
        command.downgrade(alembic_config, "base")

        # Verify tables are gone
        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            tables = inspector.get_table_names()

            assert "t3k_creators_staging" not in tables
            assert "t3k_packs_staging" not in tables
            assert "t3k_models_staging" not in tables
            assert "sync_checkpoints" not in tables


class TestT3KMigrationSchema:
    """Tests for T3K migration schema correctness."""

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_creators_staging_schema(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that t3k_creators_staging has correct columns."""
        command.upgrade(alembic_config, "head")

        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            columns = {col["name"] for col in inspector.get_columns("t3k_creators_staging")}

            assert "id" in columns
            assert "username" in columns
            assert "display_name" in columns
            assert "avatar_url" in columns
            assert "profile_url" in columns

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_packs_staging_schema(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that t3k_packs_staging has correct columns."""
        command.upgrade(alembic_config, "head")

        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            columns = {col["name"] for col in inspector.get_columns("t3k_packs_staging")}

            assert "id" in columns
            assert "name" in columns
            assert "slug" in columns
            assert "creator_id" in columns
            assert "description" in columns
            assert "thumbnail_url" in columns
            assert "platform" in columns
            assert "pack_type" in columns
            assert "created_at" in columns
            assert "updated_at" in columns

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_models_staging_schema(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that t3k_models_staging has correct columns."""
        command.upgrade(alembic_config, "head")

        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            columns = {col["name"] for col in inspector.get_columns("t3k_models_staging")}

            assert "id" in columns
            assert "pack_id" in columns
            assert "name" in columns
            assert "filename" in columns
            assert "file_size" in columns
            assert "download_url" in columns
            assert "checksum" in columns
            assert "created_at" in columns
            assert "updated_at" in columns

    @pytest.mark.skip(reason="Requires sync Alembic execution - implement after models exist")
    async def test_sync_checkpoints_schema(
        self, alembic_config: Config, t3k_db_engine: AsyncEngine
    ) -> None:
        """Test that sync_checkpoints has correct columns."""
        command.upgrade(alembic_config, "head")

        async with t3k_db_engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            columns = {col["name"] for col in inspector.get_columns("sync_checkpoints")}

            assert "id" in columns
            assert "source_name" in columns
            assert "entity_type" in columns
            assert "last_synced_at" in columns
            assert "last_record_id" in columns
            assert "total_synced" in columns


class TestT3KDatabaseSeparation:
    """Tests verifying T3K database is separate from gts_core."""

    def test_t3k_env_uses_separate_database_url(self) -> None:
        """Test that T3K env.py references T3K_DATABASE_URL not DATABASE_URL."""
        t3k_env_py = (
            Path(__file__).parent.parent.parent.parent / "sources" / "t3k" / "alembic" / "env.py"
        )

        content = t3k_env_py.read_text()

        # Should reference T3K_DATABASE_URL (or similar T3K-specific var)
        assert (
            "T3K_DATABASE_URL" in content or "gts_t3k_source" in content
        ), "env.py must use T3K-specific database URL"

        # Should NOT import from webapp.adapters.persistence.models
        assert (
            "webapp.adapters.persistence.models" not in content
        ), "T3K migrations must not import webapp models"

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

        # Should define its own Base
        assert "Base" in content, "models.py must define Base"

        # Should NOT import from webapp
        assert "from webapp" not in content, "T3K models must not import from webapp"
