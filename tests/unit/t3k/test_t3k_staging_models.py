"""Unit tests for T3K staging ORM models.

Tests the staging table models that mirror T3K domain entities.
These models live in the gts_t3k_source database, separate from gts_core.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy.exc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import (
    Base,
    SyncCheckpoint,
    T3KCreatorStaging,
    T3KModelStaging,
    T3KPackStaging,
)
from source_t3k.domain.entities import T3KCreator, T3KModel, T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session with transaction rollback."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestT3KCreatorStaging:
    """Tests for T3KCreatorStaging ORM model."""

    async def test_create_creator_staging(self, session: AsyncSession) -> None:
        """Test creating a creator staging record."""
        creator = T3KCreatorStaging(
            id="creator123",
            username="test_creator",
            display_name="Test Creator",
            avatar_url="https://example.com/avatar.jpg",
            profile_url="https://tone3000.com/user/test_creator",
        )
        session.add(creator)
        await session.commit()

        result = await session.execute(select(T3KCreatorStaging))
        saved = result.scalar_one()
        assert saved.id == "creator123"
        assert saved.username == "test_creator"
        assert saved.display_name == "Test Creator"
        assert saved.avatar_url == "https://example.com/avatar.jpg"
        assert saved.profile_url == "https://tone3000.com/user/test_creator"

    async def test_creator_from_domain_entity(self, session: AsyncSession) -> None:
        """Test creating staging model from domain entity."""
        domain_entity = T3KCreator(
            id="creator456",
            username="domain_creator",
            display_name="Domain Creator",
            avatar_url="https://example.com/domain.jpg",
            profile_url="https://tone3000.com/user/domain_creator",
        )

        staging = T3KCreatorStaging.from_domain(domain_entity)
        session.add(staging)
        await session.commit()

        result = await session.execute(select(T3KCreatorStaging))
        saved = result.scalar_one()
        assert saved.id == domain_entity.id
        assert saved.username == domain_entity.username
        assert saved.display_name == domain_entity.display_name
        assert saved.avatar_url == domain_entity.avatar_url
        assert saved.profile_url == domain_entity.profile_url

    async def test_creator_to_domain_entity(self, session: AsyncSession) -> None:
        """Test converting staging model to domain entity."""
        staging = T3KCreatorStaging(
            id="creator789",
            username="staging_creator",
            display_name="Staging Creator",
            avatar_url="https://example.com/staging.jpg",
            profile_url="https://tone3000.com/user/staging_creator",
        )
        session.add(staging)
        await session.commit()

        domain_entity = staging.to_domain()

        assert isinstance(domain_entity, T3KCreator)
        assert domain_entity.id == staging.id
        assert domain_entity.username == staging.username
        assert domain_entity.display_name == staging.display_name
        assert domain_entity.avatar_url == staging.avatar_url
        assert domain_entity.profile_url == staging.profile_url


class TestT3KPackStaging:
    """Tests for T3KPackStaging ORM model."""

    async def test_create_pack_staging(self, session: AsyncSession) -> None:
        """Test creating a pack staging record."""
        now = datetime.now(UTC)
        pack = T3KPackStaging(
            id="pack123",
            name="Test Pack",
            slug="test-pack",
            creator_id="creator123",
            description="A test pack",
            thumbnail_url="https://example.com/pack.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=now,
            updated_at=now,
        )
        session.add(pack)
        await session.commit()

        result = await session.execute(select(T3KPackStaging))
        saved = result.scalar_one()
        assert saved.id == "pack123"
        assert saved.name == "Test Pack"
        assert saved.slug == "test-pack"
        assert saved.creator_id == "creator123"
        assert saved.description == "A test pack"
        assert saved.thumbnail_url == "https://example.com/pack.jpg"
        assert saved.platform == T3KPlatform.NAM
        assert saved.pack_type == T3KPackType.AMP

    async def test_pack_from_domain_entity(self, session: AsyncSession) -> None:
        """Test creating staging model from domain entity."""
        now = datetime.now(UTC)
        domain_entity = T3KPack(
            id="pack456",
            name="Domain Pack",
            slug="domain-pack",
            creator_id="creator456",
            description="Domain pack description",
            thumbnail_url="https://example.com/domain-pack.jpg",
            platform=T3KPlatform.AIDA_X,
            pack_type=T3KPackType.PEDAL,
            created_at=now,
            updated_at=now,
        )

        staging = T3KPackStaging.from_domain(domain_entity)
        session.add(staging)
        await session.commit()

        result = await session.execute(select(T3KPackStaging))
        saved = result.scalar_one()
        assert saved.id == domain_entity.id
        assert saved.name == domain_entity.name
        assert saved.slug == domain_entity.slug
        assert saved.creator_id == domain_entity.creator_id
        assert saved.description == domain_entity.description
        assert saved.thumbnail_url == domain_entity.thumbnail_url
        assert saved.platform == domain_entity.platform
        assert saved.pack_type == domain_entity.pack_type
        assert saved.created_at == domain_entity.created_at
        assert saved.updated_at == domain_entity.updated_at

    async def test_pack_to_domain_entity(self, session: AsyncSession) -> None:
        """Test converting staging model to domain entity."""
        now = datetime.now(UTC)
        staging = T3KPackStaging(
            id="pack789",
            name="Staging Pack",
            slug="staging-pack",
            creator_id="creator789",
            description="Staging pack description",
            thumbnail_url="https://example.com/staging-pack.jpg",
            platform=T3KPlatform.IR,
            pack_type=T3KPackType.IR,
            created_at=now,
            updated_at=now,
        )
        session.add(staging)
        await session.commit()

        domain_entity = staging.to_domain()

        assert isinstance(domain_entity, T3KPack)
        assert domain_entity.id == staging.id
        assert domain_entity.name == staging.name
        assert domain_entity.slug == staging.slug
        assert domain_entity.creator_id == staging.creator_id
        assert domain_entity.description == staging.description
        assert domain_entity.thumbnail_url == staging.thumbnail_url
        assert domain_entity.platform == staging.platform
        assert domain_entity.pack_type == staging.pack_type
        assert domain_entity.created_at == staging.created_at
        assert domain_entity.updated_at == staging.updated_at


class TestT3KModelStaging:
    """Tests for T3KModelStaging ORM model."""

    async def test_create_model_staging(self, session: AsyncSession) -> None:
        """Test creating a model staging record."""
        now = datetime.now(UTC)
        model = T3KModelStaging(
            id="model123",
            pack_id="pack123",
            name="Test Model",
            filename="test-model.nam",
            file_size=1024,
            download_url="https://example.com/test-model.nam",
            checksum="abc123",
            created_at=now,
            updated_at=now,
        )
        session.add(model)
        await session.commit()

        result = await session.execute(select(T3KModelStaging))
        saved = result.scalar_one()
        assert saved.id == "model123"
        assert saved.pack_id == "pack123"
        assert saved.name == "Test Model"
        assert saved.filename == "test-model.nam"
        assert saved.file_size == 1024
        assert saved.download_url == "https://example.com/test-model.nam"
        assert saved.checksum == "abc123"

    async def test_model_from_domain_entity(self, session: AsyncSession) -> None:
        """Test creating staging model from domain entity."""
        now = datetime.now(UTC)
        domain_entity = T3KModel(
            id="model456",
            pack_id="pack456",
            name="Domain Model",
            filename="domain-model.nam",
            file_size=2048,
            download_url="https://example.com/domain-model.nam",
            checksum="def456",
            created_at=now,
            updated_at=now,
        )

        staging = T3KModelStaging.from_domain(domain_entity)
        session.add(staging)
        await session.commit()

        result = await session.execute(select(T3KModelStaging))
        saved = result.scalar_one()
        assert saved.id == domain_entity.id
        assert saved.pack_id == domain_entity.pack_id
        assert saved.name == domain_entity.name
        assert saved.filename == domain_entity.filename
        assert saved.file_size == domain_entity.file_size
        assert saved.download_url == domain_entity.download_url
        assert saved.checksum == domain_entity.checksum
        assert saved.created_at == domain_entity.created_at
        assert saved.updated_at == domain_entity.updated_at

    async def test_model_to_domain_entity(self, session: AsyncSession) -> None:
        """Test converting staging model to domain entity."""
        now = datetime.now(UTC)
        staging = T3KModelStaging(
            id="model789",
            pack_id="pack789",
            name="Staging Model",
            filename="staging-model.nam",
            file_size=4096,
            download_url="https://example.com/staging-model.nam",
            checksum="ghi789",
            created_at=now,
            updated_at=now,
        )
        session.add(staging)
        await session.commit()

        domain_entity = staging.to_domain()

        assert isinstance(domain_entity, T3KModel)
        assert domain_entity.id == staging.id
        assert domain_entity.pack_id == staging.pack_id
        assert domain_entity.name == staging.name
        assert domain_entity.filename == staging.filename
        assert domain_entity.file_size == staging.file_size
        assert domain_entity.download_url == staging.download_url
        assert domain_entity.checksum == staging.checksum
        assert domain_entity.created_at == staging.created_at
        assert domain_entity.updated_at == staging.updated_at


class TestSyncCheckpoint:
    """Tests for SyncCheckpoint tracking model."""

    async def test_create_sync_checkpoint(self, session: AsyncSession) -> None:
        """Test creating a sync checkpoint record."""
        now = datetime.now(UTC)
        checkpoint = SyncCheckpoint(
            source_name="t3k",
            entity_type="pack",
            last_synced_at=now,
            last_record_id="pack123",
            total_synced=42,
        )
        session.add(checkpoint)
        await session.commit()

        result = await session.execute(select(SyncCheckpoint))
        saved = result.scalar_one()
        assert saved.source_name == "t3k"
        assert saved.entity_type == "pack"
        assert saved.last_synced_at == now
        assert saved.last_record_id == "pack123"
        assert saved.total_synced == 42

    async def test_update_sync_checkpoint(self, session: AsyncSession) -> None:
        """Test updating an existing checkpoint."""
        now = datetime.now(UTC)
        checkpoint = SyncCheckpoint(
            source_name="t3k",
            entity_type="model",
            last_synced_at=now,
            last_record_id="model100",
            total_synced=100,
        )
        session.add(checkpoint)
        await session.commit()

        # Update the checkpoint
        later = now + timedelta(hours=1)
        checkpoint.last_synced_at = later
        checkpoint.last_record_id = "model200"
        checkpoint.total_synced = 200
        await session.commit()

        result = await session.execute(select(SyncCheckpoint))
        saved = result.scalar_one()
        assert saved.last_synced_at == later
        assert saved.last_record_id == "model200"
        assert saved.total_synced == 200

    async def test_unique_source_entity_constraint(self, session: AsyncSession) -> None:
        """Test that source_name + entity_type must be unique."""
        now = datetime.now(UTC)
        checkpoint1 = SyncCheckpoint(
            source_name="t3k",
            entity_type="creator",
            last_synced_at=now,
            last_record_id="creator1",
            total_synced=1,
        )
        session.add(checkpoint1)
        await session.commit()

        # Attempt to create duplicate
        checkpoint2 = SyncCheckpoint(
            source_name="t3k",
            entity_type="creator",
            last_synced_at=now,
            last_record_id="creator2",
            total_synced=2,
        )
        session.add(checkpoint2)

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await session.commit()

    async def test_multiple_entity_types_allowed(self, session: AsyncSession) -> None:
        """Test that multiple entity types can exist for same source."""
        now = datetime.now(UTC)

        checkpoint_pack = SyncCheckpoint(
            source_name="t3k",
            entity_type="pack",
            last_synced_at=now,
            last_record_id="pack1",
            total_synced=10,
        )
        checkpoint_model = SyncCheckpoint(
            source_name="t3k",
            entity_type="model",
            last_synced_at=now,
            last_record_id="model1",
            total_synced=20,
        )
        checkpoint_creator = SyncCheckpoint(
            source_name="t3k",
            entity_type="creator",
            last_synced_at=now,
            last_record_id="creator1",
            total_synced=5,
        )

        session.add_all([checkpoint_pack, checkpoint_model, checkpoint_creator])
        await session.commit()

        result = await session.execute(select(SyncCheckpoint))
        all_checkpoints = result.scalars().all()
        assert len(all_checkpoints) == 3

        entity_types = {cp.entity_type for cp in all_checkpoints}
        assert entity_types == {"pack", "model", "creator"}


class TestStagingTablesExist:
    """Test that all required staging tables exist."""

    async def test_all_staging_tables_in_metadata(self, db_engine: AsyncEngine) -> None:
        """Test that all staging tables are defined in Base.metadata."""
        table_names = Base.metadata.tables.keys()

        assert "t3k_creators_staging" in table_names
        assert "t3k_packs_staging" in table_names
        assert "t3k_models_staging" in table_names
        assert "sync_checkpoints" in table_names

    async def test_staging_tables_created_in_database(
        self, db_engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """Test that staging tables exist in the database schema."""
        # SQLite specific check - query sqlite_master
        result = await session.execute(
            select("name").select_from("sqlite_master").where("type = 'table'")
        )
        tables = {row[0] for row in result.fetchall()}

        assert "t3k_creators_staging" in tables
        assert "t3k_packs_staging" in tables
        assert "t3k_models_staging" in tables
        assert "sync_checkpoints" in tables
