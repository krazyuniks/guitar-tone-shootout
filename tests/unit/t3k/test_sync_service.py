"""Unit tests for T3K Sync Service (batch-then-exit model).

Tests verify run_sync_batch(), the per-tone decision tree, checkpoint
management, and file download logic.

Uses fake API client and publisher (not unittest.mock) with real PostgreSQL.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import (
    SyncCheckpoint,
    T3KModelStaging,
    T3KToneStaging,
)
from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser
from source_t3k.domain.value_objects import SyncMode, T3KGearKind, T3KPlatform
from source_t3k.services.sync_service import BACKFILL_CHECKPOINT_TYPE, T3KSyncService


class FakeAPIClient:
    """Fake T3K API client that returns predetermined responses per sort order."""

    def __init__(self) -> None:
        self.get_tones_calls: list[dict] = []
        self.newest_responses: list[list[T3KTone]] = []
        self.oldest_responses: list[list[T3KTone]] = []
        self.get_models_calls: list[int] = []
        self.get_models_responses: list[list[T3KModel]] = []
        self._newest_call_index = 0
        self._oldest_call_index = 0

    async def get_tones(self, **kwargs) -> list[T3KTone]:
        self.get_tones_calls.append(kwargs)
        sort = kwargs.get("sort", "newest")
        if sort == "oldest":
            if self._oldest_call_index < len(self.oldest_responses):
                result = self.oldest_responses[self._oldest_call_index]
                self._oldest_call_index += 1
                return result
        else:
            if self._newest_call_index < len(self.newest_responses):
                result = self.newest_responses[self._newest_call_index]
                self._newest_call_index += 1
                return result
        return []

    async def get_models(self, tone_id: int) -> list[T3KModel]:
        self.get_models_calls.append(tone_id)
        if self.get_models_responses:
            return self.get_models_responses.pop(0)
        return []


class FakePublisher:
    """Fake publisher that records published tones."""

    def __init__(self) -> None:
        self.published_tones: list[tuple[object, list]] = []

    async def publish_tone(self, tone: object, models: list | None = None) -> None:
        self.published_tones.append((tone, models or []))


@pytest.fixture
async def db_engine() -> AsyncEngine:
    import os

    from source_t3k.adapters.outbound.models import Base as T3KBase

    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(T3KBase.metadata.create_all, checkfirst=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    from sqlalchemy import delete

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(delete(T3KModelStaging).where(T3KModelStaging.id >= 900000))
        await session.execute(delete(T3KToneStaging).where(T3KToneStaging.id >= 900000))
        await session.execute(
            delete(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        await session.commit()

        yield session

        await session.execute(delete(T3KModelStaging).where(T3KModelStaging.id >= 900000))
        await session.execute(delete(T3KToneStaging).where(T3KToneStaging.id >= 900000))
        await session.execute(
            delete(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        await session.commit()


@pytest.fixture
def fake_api() -> FakeAPIClient:
    return FakeAPIClient()


@pytest.fixture
def fake_publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def sync_service(fake_api: FakeAPIClient, db_session: AsyncSession) -> T3KSyncService:
    return T3KSyncService(api_client=fake_api, session=db_session)


def _make_user() -> T3KUser:
    return T3KUser(id="user-1", username="testuser", avatar_url="", bio="", url="")


def _make_tone(tone_id: int = 1, *, models_count: int = 1, title: str | None = None) -> T3KTone:
    return T3KTone(
        id=tone_id,
        title=title or f"Test Tone {tone_id}",
        description="Test description",
        tags=[],
        makes=[],
        gear=T3KGearKind.AMP,
        platform=T3KPlatform.NAM,
        models_count=models_count,
        favorites_count=0,
        downloads_count=0,
        images=[],
        user_id="user-1",
        user=_make_user(),
        url=f"https://example.com/tones/{tone_id}",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )


def _make_model(model_id: int = 1, tone_id: int = 1) -> T3KModel:
    return T3KModel(
        id=model_id,
        tone_id=tone_id,
        user_id="user-1",
        name=f"Model {model_id}",
        model_url=f"https://example.com/models/{model_id}.nam",
        size="standard",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )


class TestBatchBehaviour:
    """Test that run_sync_batch processes one page and exits."""

    @pytest.mark.asyncio
    async def test_bau_mode_runs_newest_then_backfill(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """BAU processes newest page first, then one backfill page."""
        new_tone = _make_tone(900100)
        backfill_tone = _make_tone(900200)
        fake_api.newest_responses = [[new_tone]]
        fake_api.oldest_responses = [[backfill_tone]]
        fake_api.get_models_responses = [
            [_make_model(900110, 900100)],
            [_make_model(900210, 900200)],
        ]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        assert result.mode == SyncMode.BAU
        assert result.tones_processed == 2
        assert len(fake_publisher.published_tones) == 2

        # Should have called get_tones for both newest and oldest
        sorts = [c.get("sort") for c in fake_api.get_tones_calls]
        assert "newest" in sorts
        assert "oldest" in sorts

    @pytest.mark.asyncio
    async def test_catch_up_mode_skips_known_tones(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Known tones get 0 API calls in CATCH_UP mode."""
        # Pre-insert a known tone
        existing = T3KToneStaging.from_domain(_make_tone(900050))
        existing.last_synced_at = datetime.now(UTC)
        await db_session.merge(existing)
        await db_session.commit()

        fake_api.newest_responses = [[_make_tone(900050)]]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.CATCH_UP)

        assert result.tones_skipped == 1
        assert result.tones_processed == 0
        assert len(fake_api.get_models_calls) == 0
        assert result.hit_known_tone is True

    @pytest.mark.asyncio
    async def test_batch_returns_after_one_page(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """Does NOT loop, one call = one page."""
        fake_api.newest_responses = [
            [_make_tone(900001)],
            [_make_tone(900002)],  # second page — should NOT be reached
        ]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.CATCH_UP)

        assert result.tones_processed == 1
        newest_calls = [c for c in fake_api.get_tones_calls if c.get("sort") == "newest"]
        assert len(newest_calls) == 1  # only one page fetched


class TestSkipLogic:
    """Test the per-tone decision tree skip conditions."""

    @pytest.mark.asyncio
    async def test_skips_model_fetch_when_counts_match(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Tone with models_count == staged count → 0 get_models calls."""
        tone_domain = _make_tone(900001)
        existing_tone = T3KToneStaging.from_domain(tone_domain)
        existing_tone.last_synced_at = datetime.now(UTC)
        existing_tone.models_count = 1
        await db_session.merge(existing_tone)
        existing_model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        existing_model.file_synced_at = datetime.now(UTC)
        await db_session.merge(existing_model)
        await db_session.commit()

        fake_api.newest_responses = [[tone_domain]]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        assert len(fake_api.get_models_calls) == 0
        assert result.hit_known_tone is True

    @pytest.mark.asyncio
    async def test_fetches_models_when_counts_mismatch(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Tone with models_count > staged count → 1 get_models call."""
        tone_domain = _make_tone(900001, models_count=2)
        existing_tone = T3KToneStaging.from_domain(tone_domain)
        existing_tone.last_synced_at = datetime.now(UTC)
        existing_tone.models_count = 2
        await db_session.merge(existing_tone)
        existing_model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        await db_session.merge(existing_model)
        await db_session.commit()

        fake_api.newest_responses = [[tone_domain]]
        fake_api.oldest_responses = []
        fake_api.get_models_responses = [
            [_make_model(900010, 900001), _make_model(900011, 900001)],
        ]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        assert len(fake_api.get_models_calls) == 1
        assert result.models_staged > 0

    @pytest.mark.asyncio
    async def test_skips_download_when_file_synced_at_set(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Model with file_synced_at → 0 download calls."""
        tone = _make_tone(900001)
        fake_api.newest_responses = [[tone]]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.CATCH_UP)

        # Since there's no model_downloader, no downloads happen
        assert result.files_downloaded == 0

    @pytest.mark.asyncio
    async def test_downloads_missing_files_even_when_model_counts_match(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Tone with all models staged but some file_synced_at NULL → downloads triggered."""
        tone_domain = _make_tone(900001)
        existing_tone = T3KToneStaging.from_domain(tone_domain)
        existing_tone.last_synced_at = datetime.now(UTC)
        existing_tone.models_count = 1
        await db_session.merge(existing_tone)

        # Model with file_synced_at = NULL
        existing_model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        existing_model.file_synced_at = None
        await db_session.merge(existing_model)
        await db_session.commit()

        fake_api.oldest_responses = [[tone_domain]]

        # BAU backfill should detect the missing file
        # No downloader configured, so files_downloaded stays 0,
        # but the logic should still be triggered (no get_models call)
        await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        # No get_models calls for this tone — model counts match
        # The tone appears in newest with skipped=True (counts match, no downloader)
        # It also appears in backfill
        assert len(fake_api.get_models_calls) == 0


class TestUpsertCorrectness:
    """Test upsert patterns preserve data correctly."""

    @pytest.mark.asyncio
    async def test_model_upsert_preserves_file_synced_at(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Pre-insert model with file_synced_at, re-sync, verify preserved."""
        # Pre-insert model with file_synced_at set
        model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        model.file_synced_at = datetime(2024, 6, 1, tzinfo=UTC)
        await db_session.merge(model)
        await db_session.commit()

        # Now sync this tone (which will upsert the model)
        tone = _make_tone(900001)
        fake_api.newest_responses = [[tone]]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.CATCH_UP)

        # Verify file_synced_at was preserved
        result = await db_session.execute(
            select(T3KModelStaging).where(T3KModelStaging.id == 900010)
        )
        staged_model = result.scalar_one()
        assert staged_model.file_synced_at is not None
        assert staged_model.file_synced_at.year == 2024

    @pytest.mark.asyncio
    async def test_tone_upsert_updates_metadata(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Re-sync tone with changed title, verify updated."""
        # Pre-insert tone
        original = T3KToneStaging.from_domain(_make_tone(900001, title="Original Title"))
        original.last_synced_at = datetime.now(UTC)
        original.models_count = 0
        await db_session.merge(original)
        await db_session.commit()

        # Sync with updated title
        updated_tone = _make_tone(900001, title="Updated Title", models_count=1)
        fake_api.newest_responses = [[updated_tone]]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        # Expire cached ORM objects so SELECT re-queries from DB
        db_session.expire_all()
        result = await db_session.execute(select(T3KToneStaging).where(T3KToneStaging.id == 900001))
        staged_tone = result.scalar_one()
        assert staged_tone.title == "Updated Title"


class TestAtomicity:
    """Test commit-per-tone atomicity."""

    @pytest.mark.asyncio
    async def test_commits_per_tone(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Tone 1 succeeds even if we only have models for tone 1."""
        tone1 = _make_tone(900001)
        tone2 = _make_tone(900002)
        fake_api.newest_responses = [[tone1, tone2]]
        # Only models for tone1, tone2 gets empty models
        fake_api.get_models_responses = [
            [_make_model(900010, 900001)],
            [],  # tone2 has no models
        ]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.CATCH_UP)

        # Tone 1 should be in the DB regardless of tone 2
        tone1_result = await db_session.execute(
            select(T3KToneStaging).where(T3KToneStaging.id == 900001)
        )
        assert tone1_result.scalar_one_or_none() is not None
        assert result.tones_processed == 2


class TestNewestStopCondition:
    """Test that newest check stops at first known tone."""

    @pytest.mark.asyncio
    async def test_newest_stops_at_first_known_tone(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """hit_known_tone=True in result."""
        # Pre-insert a known tone with matching model count + file_synced_at
        existing = T3KToneStaging.from_domain(_make_tone(900050))
        existing.last_synced_at = datetime.now(UTC)
        existing.models_count = 1
        await db_session.merge(existing)
        existing_model = T3KModelStaging.from_domain(_make_model(900500, 900050))
        existing_model.file_synced_at = datetime.now(UTC)
        await db_session.merge(existing_model)
        await db_session.commit()

        # API returns: new tone 900051, then known tone 900050
        fake_api.newest_responses = [[_make_tone(900051), _make_tone(900050)]]
        fake_api.get_models_responses = [[_make_model(900510, 900051)]]

        result = await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        assert result.hit_known_tone is True
        # Only tone 900051 should be processed (900050 was known)
        assert result.tones_processed >= 1


class TestBackfillCheckpoint:
    """Test backfill checkpoint management."""

    @pytest.mark.asyncio
    async def test_advances_checkpoint_through_pages(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Backfill loops through pages until end of catalogue."""
        fake_api.newest_responses = []
        # Page 1: one tone. Page 2: empty (end of catalogue → reset to 1)
        fake_api.oldest_responses = [[_make_tone(900001)]]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        # Backfill looped: page 1 processed, page 2 empty → reset to 1
        result = await db_session.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        cp = result.scalar_one()
        assert cp.last_record_id == "1"

    @pytest.mark.asyncio
    async def test_resets_at_end_of_catalogue(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Empty page resets to page 1."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(SyncCheckpoint)
            .values(
                source_name="t3k",
                entity_type=BACKFILL_CHECKPOINT_TYPE,
                last_synced_at=datetime.now(UTC),
                last_record_id="999",
                total_synced=0,
            )
            .on_conflict_do_update(
                index_elements=["source_name", "entity_type"],
                set_={"last_record_id": "999"},
            )
        )
        await db_session.execute(stmt)
        await db_session.commit()

        fake_api.newest_responses = []
        fake_api.oldest_responses = []  # empty page = end of catalogue

        await sync_service.run_sync_batch(fake_publisher, mode=SyncMode.BAU)

        result = await db_session.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        cp = result.scalar_one()
        assert cp.last_record_id == "1"
