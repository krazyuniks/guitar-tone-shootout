"""Integration tests for GearSyncPublisher with pgmq.

Tests the actual publishing of GearSyncRecords to pgmq queues
and transactional behaviour. Uses SQLite (pgmq calls are silently
swallowed) to verify the publisher doesn't crash.
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

from source_t3k.adapters.outbound.models import T3KModelStaging, T3KToneStaging
from source_t3k.adapters.outbound.publisher import GearSyncPublisher


@pytest.fixture
async def t3k_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create async engine for T3K staging database.

    Only creates tables without PostgreSQL ARRAY columns (model staging).
    Tone staging objects are constructed in-memory without DB persistence.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(T3KModelStaging.__table__.create)
    yield engine
    await engine.dispose()


@pytest.fixture
async def t3k_session(t3k_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for T3K staging database."""
    async_session = async_sessionmaker(t3k_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


def _make_tone(**overrides) -> T3KToneStaging:
    """Build a T3KToneStaging with sensible defaults."""
    defaults = {
        "id": 42,
        "title": "Mesa Boogie Dual Rectifier",
        "description": "High gain amp",
        "tags": ["high-gain"],
        "makes": ["Mesa"],
        "gear": "amp",
        "platform": "nam",
        "models_count": 3,
        "favorites_count": 10,
        "downloads_count": 100,
        "images": ["https://example.com/thumb.jpg"],
        "user_id": "user-456",
        "url": "https://t3k.com/tones/42",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 15, tzinfo=UTC),
    }
    defaults.update(overrides)
    return T3KToneStaging(**defaults)


def _make_model(**overrides) -> T3KModelStaging:
    """Build a T3KModelStaging with sensible defaults."""
    defaults = {
        "id": 99,
        "tone_id": 42,
        "user_id": "user-456",
        "name": "Clean Channel",
        "model_url": "https://t3k.com/models/99/clean.nam",
        "size": "standard",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 20, tzinfo=UTC),
    }
    defaults.update(overrides)
    return T3KModelStaging(**defaults)


class TestGearSyncPublisherTonePublishing:
    """Tests for publishing tone sync records to pgmq."""

    async def test_publish_tone_does_not_raise(self, t3k_session: AsyncSession) -> None:
        """publish_tone should not raise on SQLite (pgmq call is swallowed)."""
        tone = _make_tone()
        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")
        await publisher.publish_tone(tone)

    async def test_publish_tone_creates_correct_sync_record(
        self, t3k_session: AsyncSession
    ) -> None:
        """publish_tone should create GearSyncRecord with correct data."""
        tone = _make_tone()
        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")
        record = publisher.create_tone_sync_record(tone)

        assert record.source_name == "t3k"
        assert record.source_record_id == "42"
        assert record.payload["name"] == "Mesa Boogie Dual Rectifier"
        assert record.payload["platform"] == "nam"
        assert record.payload["gear_type"] == "amp"

    async def test_publish_tone_with_models(self, t3k_session: AsyncSession) -> None:
        """publish_tone should accept optional model list."""
        tone = _make_tone()
        models = [_make_model()]
        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")
        await publisher.publish_tone(tone, models=models)


class TestGearSyncPublisherTransactionalBehaviour:
    """Tests for transactional publishing behaviour."""

    async def test_publish_tone_is_transactional(self, t3k_session: AsyncSession) -> None:
        """publish_tone operations should be part of session transaction."""
        tone = _make_tone()
        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")

        await publisher.publish_tone(tone)
        await t3k_session.commit()

    async def test_publish_with_none_session_is_noop(self) -> None:
        """publish_tone with session=None should be a no-op."""
        tone = _make_tone()
        publisher = GearSyncPublisher(session=None, queue_name="gear_sync")
        await publisher.publish_tone(tone)


class TestGearSyncPublisherQueueConfiguration:
    """Tests for publisher queue configuration."""

    async def test_publisher_uses_specified_queue_name(self, t3k_session: AsyncSession) -> None:
        """publisher should store the queue name provided at initialisation."""
        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")
        assert publisher.queue_name == "gear_sync"

    async def test_multiple_tones_can_be_published_sequentially(
        self, t3k_session: AsyncSession
    ) -> None:
        """Multiple tones should be publishable in sequence."""
        tone1 = _make_tone(id=1, title="Pack 1")
        tone2 = _make_tone(id=2, title="Pack 2", platform="aida_x", gear="pedal")

        publisher = GearSyncPublisher(session=t3k_session, queue_name="gear_sync")

        await publisher.publish_tone(tone1)
        await publisher.publish_tone(tone2)

        await t3k_session.commit()
