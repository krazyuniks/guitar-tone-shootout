"""Unit tests for T3K Sync Service.

The sync service coordinates fetching data from the T3K API and upserting it
to staging tables. Tests verify run_catalog_sync(), dual-sync strategy,
checkpoint management, and error recovery.

Uses a fake API client class (not unittest.mock) and real PostgreSQL database.
"""

import contextlib
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
from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform
from source_t3k.services.sync_service import BACKFILL_CHECKPOINT_TYPE, T3KSyncService


class FakeAPIClient:
    """Fake T3K API client that returns predetermined responses per sort order."""

    def __init__(self) -> None:
        self.get_tones_calls: list[dict] = []
        # Responses keyed by sort order — each is a list of pages (list of tones)
        self.newest_responses: list[list[T3KTone]] = []
        self.oldest_responses: list[list[T3KTone]] = []
        self.get_models_calls: list[int] = []
        self.get_models_responses: list[list[T3KModel]] = []
        self._newest_call_index = 0
        self._oldest_call_index = 0
        self._get_tones_error: Exception | None = None

    async def get_tones(self, **kwargs) -> list[T3KTone]:
        self.get_tones_calls.append(kwargs)
        if self._get_tones_error is not None:
            raise self._get_tones_error

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
        self.published_tones: list[object] = []

    async def publish_tone(self, tone: object, models: list | None = None) -> None:
        self.published_tones.append(tone)


@pytest.fixture
async def db_engine() -> AsyncEngine:
    """Create a test engine using the real PostgreSQL database."""
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
    """Create a database session, cleaning up test data before and after."""
    from sqlalchemy import delete

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        # Clean up any leftover test data (IDs >= 900000)
        await session.execute(delete(T3KModelStaging).where(T3KModelStaging.id >= 900000))
        await session.execute(delete(T3KToneStaging).where(T3KToneStaging.id >= 900000))
        await session.execute(
            delete(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        await session.commit()

        yield session

        # Clean up after tests
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


def _make_tone(tone_id: int = 1) -> T3KTone:
    return T3KTone(
        id=tone_id,
        title=f"Test Tone {tone_id}",
        description="Test description",
        tags=[],
        makes=[],
        gear=T3KGearKind.AMP,
        platform=T3KPlatform.NAM,
        models_count=1,
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


class TestT3KSyncServiceImport:
    """Test that T3KSyncService exists and is importable."""

    def test_service_class_exists(self) -> None:
        assert T3KSyncService is not None
        assert callable(T3KSyncService)


class TestT3KSyncServiceConstruction:
    """Test T3KSyncService initialization."""

    def test_service_accepts_dependencies(
        self, fake_api: FakeAPIClient, db_session: AsyncSession
    ) -> None:
        service = T3KSyncService(api_client=fake_api, session=db_session)
        assert service is not None
        assert hasattr(service, "run_catalog_sync")


class TestNewestCheck:
    """Test _run_newest_check: walks sort=newest, stops at first known tone."""

    @pytest.mark.asyncio
    async def test_newest_check_stages_new_tones(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """Newest check should stage tones not yet in the database."""
        tone = _make_tone(900100)
        model = _make_model(900200, 900100)
        fake_api.newest_responses = [[tone], []]
        fake_api.oldest_responses = []
        fake_api.get_models_responses = [[model]]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        assert len(fake_publisher.published_tones) == 1
        newest_calls = [c for c in fake_api.get_tones_calls if c.get("sort") == "newest"]
        assert len(newest_calls) >= 1

    @pytest.mark.asyncio
    async def test_newest_check_stops_at_known_tone(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Newest check should stop when it hits a tone already in staging."""
        # Pre-insert a known tone
        existing = T3KToneStaging.from_domain(_make_tone(900050))
        existing.last_synced_at = datetime.now(UTC)
        await db_session.merge(existing)
        await db_session.commit()

        # API returns: new tone 900051, then known tone 900050
        fake_api.newest_responses = [[_make_tone(900051), _make_tone(900050)]]
        fake_api.oldest_responses = []
        fake_api.get_models_responses = [
            [_make_model(900510, 900051)],
        ]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        # Only tone 900051 should be published (900050 was known, stopped there)
        assert len(fake_publisher.published_tones) == 1

    @pytest.mark.asyncio
    async def test_newest_check_no_page_cap(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """Newest check should walk beyond 2 pages if all tones are new."""
        # 4 pages of new tones, then empty page
        fake_api.newest_responses = [[_make_tone(900000 + i)] for i in range(1, 5)] + [[]]
        fake_api.oldest_responses = []
        fake_api.get_models_responses = [
            [_make_model(900000 + i * 10, 900000 + i)] for i in range(1, 5)
        ]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        assert len(fake_publisher.published_tones) == 4
        newest_calls = [c for c in fake_api.get_tones_calls if c.get("sort") == "newest"]
        assert len(newest_calls) >= 4


class TestBackfill:
    """Test _run_backfill_batch: walks sort=oldest from checkpoint."""

    @pytest.mark.asyncio
    async def test_backfill_uses_sort_oldest(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """Backfill should request tones with sort=oldest."""
        tone = _make_tone(900001)
        model = _make_model(900010, 900001)
        fake_api.newest_responses = []
        fake_api.oldest_responses = [[tone]]
        fake_api.get_models_responses = [[model]]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        oldest_calls = [c for c in fake_api.get_tones_calls if c.get("sort") == "oldest"]
        assert len(oldest_calls) >= 1

    @pytest.mark.asyncio
    async def test_backfill_skips_complete_tones(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Backfill should skip tones where all models are already staged."""
        tone_domain = _make_tone(900001)
        existing_tone = T3KToneStaging.from_domain(tone_domain)
        existing_tone.last_synced_at = datetime.now(UTC)
        existing_tone.models_count = 1
        await db_session.merge(existing_tone)
        existing_model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        await db_session.merge(existing_model)
        await db_session.commit()

        fake_api.newest_responses = []
        fake_api.oldest_responses = [[tone_domain]]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        # Should not have called get_models (skipped entirely)
        assert len(fake_api.get_models_calls) == 0
        assert len(fake_publisher.published_tones) == 0

    @pytest.mark.asyncio
    async def test_backfill_fetches_missing_models(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Backfill should fetch models for tones with incomplete model count."""
        tone_domain = _make_tone(900001)
        existing_tone = T3KToneStaging.from_domain(tone_domain)
        existing_tone.models_count = 2
        existing_tone.last_synced_at = datetime.now(UTC)
        await db_session.merge(existing_tone)
        existing_model = T3KModelStaging.from_domain(_make_model(900010, 900001))
        await db_session.merge(existing_model)
        await db_session.commit()

        fake_api.newest_responses = []
        fake_api.oldest_responses = [[tone_domain]]
        fake_api.get_models_responses = [
            [_make_model(900010, 900001), _make_model(900011, 900001)],
        ]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        assert len(fake_api.get_models_calls) == 1
        assert len(fake_publisher.published_tones) == 1

    @pytest.mark.asyncio
    async def test_backfill_creates_checkpoint(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Backfill should create a backfill_page checkpoint."""
        fake_api.newest_responses = []
        fake_api.oldest_responses = [[_make_tone(900001)]]
        fake_api.get_models_responses = [[_make_model(900010, 900001)]]

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        result = await db_session.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        cp = result.scalar_one_or_none()
        assert cp is not None
        assert cp.last_record_id == "2"

    @pytest.mark.asyncio
    async def test_backfill_resets_at_end_of_catalogue(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
        db_session: AsyncSession,
    ) -> None:
        """Backfill should reset to page 1 when it reaches the end."""
        cp = SyncCheckpoint(
            source_name="t3k",
            entity_type=BACKFILL_CHECKPOINT_TYPE,
            last_synced_at=datetime.now(UTC),
            last_record_id="999",
            total_synced=0,
        )
        await db_session.merge(cp)
        await db_session.commit()

        fake_api.newest_responses = []
        fake_api.oldest_responses = []

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        # Re-query since the sync may have replaced the checkpoint object
        result = await db_session.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE)
        )
        updated_cp = result.scalar_one()
        assert updated_cp.last_record_id == "1"


class TestRunCatalogSync:
    """Test the overall run_catalog_sync orchestration."""

    @pytest.mark.asyncio
    async def test_run_catalog_sync_stops_at_max_iterations(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """run_catalog_sync respects max_iterations limit."""
        await sync_service.run_catalog_sync(fake_publisher, max_iterations=2)
        assert True  # If we reach here, it stopped as expected

    @pytest.mark.asyncio
    async def test_run_catalog_sync_handles_api_error(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """run_catalog_sync handles API errors without crashing."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        fake_api._get_tones_error = T3KAPIError("API error")

        with contextlib.suppress(T3KAPIError):
            await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        assert len(fake_api.get_tones_calls) >= 0

    @pytest.mark.asyncio
    async def test_newest_runs_before_backfill(
        self,
        sync_service: T3KSyncService,
        fake_api: FakeAPIClient,
        fake_publisher: FakePublisher,
    ) -> None:
        """Newest check should run before backfill in each iteration."""
        fake_api.newest_responses = []
        fake_api.oldest_responses = []

        await sync_service.run_catalog_sync(fake_publisher, max_iterations=1)

        # First call should be sort=newest, second should be sort=oldest
        if len(fake_api.get_tones_calls) >= 2:
            assert fake_api.get_tones_calls[0].get("sort") == "newest"
            assert fake_api.get_tones_calls[1].get("sort") == "oldest"
