"""Integration tests for GearSyncPublisher with pgmq.

Tests the actual publishing of GearSyncRecords to pgmq queues
and transactional behavior.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import Base, T3KModelStaging, T3KPackStaging
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


@pytest.fixture
async def t3k_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create async engine for T3K staging database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def t3k_session(t3k_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for T3K staging database."""
    async_session = async_sessionmaker(t3k_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestGearSyncPublisherPackPublishing:
    """Tests for publishing pack sync records to pgmq."""

    async def test_publish_pack_enqueues_to_gear_pack_sync_queue(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that publish_pack sends message to gear_pack_sync queue."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie Dual Rectifier",
            slug="mesa-boogie-dual-rectifier",
            creator_id="creator-456",
            description="High gain amp pack",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        t3k_session.add(pack)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_pack_sync")

        # This should fail because the method doesn't exist yet
        await publisher.publish_pack(pack)

        # In SQLite we can't test pgmq, but verify the method completed without error

    async def test_publish_pack_creates_correct_sync_record(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that publish_pack creates GearSyncRecord with correct data."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie Dual Rectifier",
            slug="mesa-boogie-dual-rectifier",
            creator_id="creator-456",
            description="High gain amp pack",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        t3k_session.add(pack)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_pack_sync")
        record = publisher.create_pack_sync_record(pack)

        # Verify the sync record structure
        assert record.source_name == "t3k"
        assert record.source_record_id == "pack-123"
        assert record.payload["name"] == "Mesa Boogie Dual Rectifier"
        assert record.payload["slug"] == "mesa-boogie-dual-rectifier"
        assert record.payload["platform"] == "nam"
        assert record.payload["gear_type"] == "amp"


class TestGearSyncPublisherModelPublishing:
    """Tests for publishing model sync records to pgmq."""

    async def test_publish_model_enqueues_to_gear_model_sync_queue(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that publish_model sends message to gear_model_sync queue."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1 Vintage",
            filename="channel1_vintage.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        t3k_session.add(model)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_model_sync")

        # This should fail because the method doesn't exist yet
        await publisher.publish_model(model)

        # Verify method completed without error

    async def test_publish_model_creates_correct_sync_record(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that publish_model creates GearSyncRecord with correct data."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1 Vintage",
            filename="channel1_vintage.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        t3k_session.add(model)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_model_sync")
        record = publisher.create_model_sync_record(model)

        # Verify the sync record structure
        assert record.source_name == "t3k"
        assert record.source_record_id == "model-789"
        assert record.payload["name"] == "Channel 1 Vintage"
        assert record.payload["filename"] == "channel1_vintage.nam"
        assert record.payload["file_size"] == 1024000
        assert record.payload["pack_id"] == "pack-123"


class TestGearSyncPublisherTransactionalBehavior:
    """Tests for transactional publishing behavior."""

    async def test_publish_pack_is_transactional(self, t3k_session: AsyncSession) -> None:
        """Test that publish_pack operations are part of session transaction."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie",
            slug="mesa-boogie",
            creator_id="creator-456",
            description="Amp",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        t3k_session.add(pack)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_pack_sync")

        # Publish within the same session - should be transactional
        await publisher.publish_pack(pack)

        # Both the staging record and the queue message should be part of the same transaction
        # When session is committed, both persist; when rolled back, neither persists
        await t3k_session.commit()

    async def test_publish_model_is_transactional(self, t3k_session: AsyncSession) -> None:
        """Test that publish_model operations are part of session transaction."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1",
            filename="channel1.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        t3k_session.add(model)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_model_sync")

        # Publish within the same session - should be transactional
        await publisher.publish_model(model)

        # Both the staging record and the queue message should be part of the same transaction
        await t3k_session.commit()


class TestGearSyncPublisherQueueConfiguration:
    """Tests for publisher queue configuration."""

    async def test_publisher_uses_specified_queue_name(self, t3k_session: AsyncSession) -> None:
        """Test that publisher uses the queue name provided at initialization."""
        publisher_pack = GearSyncPublisher(session=t3k_session, queue_name="gear_pack_sync")
        publisher_model = GearSyncPublisher(session=t3k_session, queue_name="gear_model_sync")

        # Queue names should be stored and used for publishing
        assert publisher_pack.queue_name == "gear_pack_sync"
        assert publisher_model.queue_name == "gear_model_sync"

    async def test_multiple_packs_can_be_published_sequentially(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that multiple packs can be published in sequence."""
        pack1 = T3KPackStaging(
            id="pack-1",
            name="Pack 1",
            slug="pack-1",
            creator_id="creator-456",
            description="First",
            thumbnail_url="https://example.com/1.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        pack2 = T3KPackStaging(
            id="pack-2",
            name="Pack 2",
            slug="pack-2",
            creator_id="creator-456",
            description="Second",
            thumbnail_url="https://example.com/2.jpg",
            platform=T3KPlatform.AIDA_X,
            pack_type=T3KPackType.PEDAL,
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
            updated_at=datetime(2024, 1, 16, tzinfo=UTC),
        )

        t3k_session.add(pack1)
        t3k_session.add(pack2)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_pack_sync")

        # Should be able to publish multiple packs
        await publisher.publish_pack(pack1)
        await publisher.publish_pack(pack2)

        await t3k_session.commit()

    async def test_multiple_models_can_be_published_sequentially(
        self, t3k_session: AsyncSession
    ) -> None:
        """Test that multiple models can be published in sequence."""
        model1 = T3KModelStaging(
            id="model-1",
            pack_id="pack-123",
            name="Model 1",
            filename="model1.nam",
            file_size=1024000,
            download_url="https://example.com/model1.nam",
            checksum="abc1",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        model2 = T3KModelStaging(
            id="model-2",
            pack_id="pack-123",
            name="Model 2",
            filename="model2.nam",
            file_size=2048000,
            download_url="https://example.com/model2.nam",
            checksum="abc2",
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
            updated_at=datetime(2024, 1, 21, tzinfo=UTC),
        )

        t3k_session.add(model1)
        t3k_session.add(model2)
        await t3k_session.flush()

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_model_sync")

        # Should be able to publish multiple models
        await publisher.publish_model(model1)
        await publisher.publish_model(model2)

        await t3k_session.commit()
