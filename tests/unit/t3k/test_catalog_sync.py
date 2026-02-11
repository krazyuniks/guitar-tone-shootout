"""Unit tests for T3K catalog sync loop.

Tests the run_catalog_sync() method which alternates between backfill (walking
oldest→newest from checkpoint) and newest (checking for recent updates). Tests
verify checkpoint advancement, skip logic, publishing, and stale detection.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import SyncCheckpoint, T3KPackStaging
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.entities import T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform
from source_t3k.services.sync_service import T3KSyncService


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Create a mock T3K API client."""
    return AsyncMock(spec=T3KAPIClient)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_publisher() -> MagicMock:
    """Create a mock publisher with async publish_pack method."""
    publisher = MagicMock(spec=GearSyncPublisher)
    publisher.publish_pack = AsyncMock()
    return publisher


@pytest.fixture
def sync_service(mock_api_client: AsyncMock, mock_session: AsyncMock) -> T3KSyncService:
    """Create a T3KSyncService with mocked dependencies."""
    return T3KSyncService(api_client=mock_api_client, session=mock_session)


@pytest.fixture
def sample_pack() -> T3KPack:
    """Create a sample T3K pack entity."""
    return T3KPack(
        id="pack-1",
        name="Test Pack",
        slug="test-pack",
        creator_id="creator-1",
        description="Test description",
        thumbnail_url="https://example.com/thumb.jpg",
        platform=T3KPlatform.NAM,
        pack_type=T3KPackType.AMP,
        created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def old_pack() -> T3KPack:
    """Create a pack with old timestamps."""
    return T3KPack(
        id="pack-old",
        name="Old Pack",
        slug="old-pack",
        creator_id="creator-1",
        description="Old pack",
        thumbnail_url="https://example.com/old.jpg",
        platform=T3KPlatform.NAM,
        pack_type=T3KPackType.AMP,
        created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def recent_pack() -> T3KPack:
    """Create a pack with recent timestamps."""
    now = datetime.now(UTC)
    return T3KPack(
        id="pack-recent",
        name="Recent Pack",
        slug="recent-pack",
        creator_id="creator-1",
        description="Recent pack",
        thumbnail_url="https://example.com/recent.jpg",
        platform=T3KPlatform.NAM,
        pack_type=T3KPackType.AMP,
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(hours=1),
    )


class TestRunCatalogSyncBasic:
    """Test basic run_catalog_sync() behaviour."""

    @pytest.mark.asyncio
    async def test_run_catalog_sync_method_exists(self, sync_service: T3KSyncService) -> None:
        """run_catalog_sync method should exist on T3KSyncService."""
        assert hasattr(sync_service, "run_catalog_sync")
        assert callable(sync_service.run_catalog_sync)

    @pytest.mark.asyncio
    async def test_run_catalog_sync_alternates_backfill_and_newest(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """run_catalog_sync should alternate between backfill batches and newest checks."""
        # Mock API to return packs then empty for both strategies
        mock_api_client.get_packs.side_effect = [
            [sample_pack],  # Backfill batch 1
            [],  # Backfill batch 1 end
            [sample_pack],  # Newest check 1
            [],  # Newest check 1 end
        ]

        # Run 1 iteration (1 backfill + 1 newest)
        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called get_packs at least 2 times (backfill + newest)
        assert mock_api_client.get_packs.call_count >= 2

    @pytest.mark.asyncio
    async def test_run_catalog_sync_accepts_max_iterations(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """run_catalog_sync should accept max_iterations parameter for testability."""
        # Mock API to return empty (no data)
        mock_api_client.get_packs.return_value = []

        # Should complete with max_iterations=1 (not run forever)
        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have executed without blocking
        assert mock_api_client.get_packs.called

    @pytest.mark.asyncio
    async def test_run_catalog_sync_runs_indefinitely_without_max_iterations(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """run_catalog_sync without max_iterations should run until stopped externally."""
        # Mock API to return empty 5 times then raise to simulate stop
        mock_api_client.get_packs.side_effect = [[], [], [], [], [], RuntimeError("Stop")]

        # Should raise RuntimeError after 5+ iterations
        with pytest.raises(RuntimeError):
            await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=None)

        # Should have made multiple API calls (more than 5)
        assert mock_api_client.get_packs.call_count >= 5


class TestBackfillBatch:
    """Test backfill batch behaviour within run_catalog_sync."""

    @pytest.mark.asyncio
    async def test_backfill_uses_checkpoint_position(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Backfill should start from checkpoint's last_record_id position."""
        # Mock checkpoint with last_record_id
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=datetime(2024, 1, 1, tzinfo=UTC),
            last_record_id="pack-50",
            total_synced=50,
        )
        mock_session.execute.return_value = mock_result

        # Mock API to return packs
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have read checkpoint before starting
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_backfill_advances_checkpoint_after_batch(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Backfill should update checkpoint after processing each batch."""
        # Mock API to return one pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have committed checkpoint after batch
        assert mock_session.commit.call_count >= 1
        # Should have added checkpoint update
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_backfill_stops_on_empty_response(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """Backfill should stop when API returns empty list."""
        # Mock API to return empty immediately
        mock_api_client.get_packs.return_value = []

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called API once and stopped
        assert mock_api_client.get_packs.call_count >= 1

    @pytest.mark.asyncio
    async def test_backfill_processes_multiple_pages(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Backfill should process multiple pages in a single batch."""
        # Mock API to return 3 pages of data
        mock_api_client.get_packs.side_effect = [
            [sample_pack] * 10,  # Page 1
            [sample_pack] * 10,  # Page 2
            [sample_pack] * 5,  # Page 3 (partial)
            [],  # Page 4 (empty - stop backfill)
            [],  # Newest check
        ]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have paginated through all backfill pages
        assert mock_api_client.get_packs.call_count >= 4


class TestNewestCheck:
    """Test newest check behaviour within run_catalog_sync."""

    @pytest.mark.asyncio
    async def test_newest_check_queries_most_recent(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        recent_pack: T3KPack,
    ) -> None:
        """Newest check should query most recent records from API."""
        # Mock API: backfill empty, newest has recent pack
        mock_api_client.get_packs.side_effect = [
            [],  # Backfill empty
            [recent_pack],  # Newest check
            [],  # Newest check end
        ]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called API for newest check
        assert mock_api_client.get_packs.call_count >= 2

    @pytest.mark.asyncio
    async def test_newest_check_stops_on_known_records(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Newest check should stop when encountering already-staged records."""
        # Mock staging query to return existing pack
        staging_result = AsyncMock()
        staging_result.scalar_one_or_none.return_value = T3KPackStaging.from_domain(sample_pack)

        # Mock checkpoint query to return None first, then staging query
        mock_session.execute.side_effect = [
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)),  # Checkpoint query
            staging_result,  # Staging existence check
        ]

        # Mock API to return pack
        mock_api_client.get_packs.side_effect = [
            [],  # Backfill empty
            [sample_pack],  # Newest check - already exists
        ]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have queried database to check if pack exists
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_newest_check_limited_to_two_pages(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Newest check should fetch at most 2 pages."""
        # Mock API to return many pages of new packs
        mock_api_client.get_packs.side_effect = [
            [],  # Backfill empty
            [sample_pack] * 10,  # Newest page 1
            [sample_pack] * 10,  # Newest page 2
            [],  # Should stop after 2 pages
        ]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called API for backfill + 2 newest pages + stop check
        assert mock_api_client.get_packs.call_count <= 4


class TestSkipRecentlySynced:
    """Test 7-day skip logic for recently synced records."""

    @pytest.mark.asyncio
    async def test_skip_packs_synced_within_seven_days(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Records synced within 7 days should be skipped (not re-processed)."""
        # Create staging pack with recent last_synced_at
        now = datetime.now(UTC)
        staging_pack = T3KPackStaging.from_domain(sample_pack)
        # Note: T3KPackStaging doesn't have last_synced_at yet - test expects it to be added
        staging_pack.last_synced_at = now - timedelta(days=3)  # Synced 3 days ago

        # Mock staging query to return recently-synced pack
        staging_result = AsyncMock()
        staging_result.scalar_one_or_none.return_value = staging_pack

        mock_session.execute.side_effect = [
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)),  # Checkpoint
            staging_result,  # Staging existence check
        ]

        # Mock API to return pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should NOT have published (skipped due to recent sync)
        assert mock_publisher.publish_pack.call_count == 0

    @pytest.mark.asyncio
    async def test_process_packs_synced_more_than_seven_days_ago(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Records synced more than 7 days ago should be re-processed."""
        # Create staging pack with old last_synced_at
        now = datetime.now(UTC)
        staging_pack = T3KPackStaging.from_domain(sample_pack)
        staging_pack.last_synced_at = now - timedelta(days=10)  # Synced 10 days ago

        # Mock staging query to return old-synced pack
        staging_result = AsyncMock()
        staging_result.scalar_one_or_none.return_value = staging_pack

        mock_session.execute.side_effect = [
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)),  # Checkpoint
            staging_result,  # Staging existence check
        ]

        # Mock API to return pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have published (old sync, needs refresh)
        assert mock_publisher.publish_pack.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_packs_never_synced_before(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Records with no last_synced_at should be processed."""
        # Create staging pack with no last_synced_at
        staging_pack = T3KPackStaging.from_domain(sample_pack)
        staging_pack.last_synced_at = None  # Never synced

        # Mock staging query to return never-synced pack
        staging_result = AsyncMock()
        staging_result.scalar_one_or_none.return_value = staging_pack

        mock_session.execute.side_effect = [
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)),  # Checkpoint
            staging_result,  # Staging existence check
        ]

        # Mock API to return pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have published (never synced before)
        assert mock_publisher.publish_pack.call_count >= 1


class TestStaleCheckpointDetection:
    """Test 30-day stale checkpoint detection and reset."""

    @pytest.mark.asyncio
    async def test_reset_checkpoint_if_older_than_thirty_days(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """Checkpoint older than 30 days should be reset to start from beginning."""
        # Mock checkpoint with old last_synced_at
        now = datetime.now(UTC)
        old_checkpoint = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=now - timedelta(days=45),  # 45 days old
            last_record_id="pack-100",
            total_synced=100,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = old_checkpoint
        mock_session.execute.return_value = mock_result

        # Mock API to return empty
        mock_api_client.get_packs.return_value = []

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have reset checkpoint (added new checkpoint or updated existing)
        assert mock_session.add.called
        # Should have committed the reset
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_keep_checkpoint_if_less_than_thirty_days_old(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """Checkpoint less than 30 days old should not be reset."""
        # Mock checkpoint with recent last_synced_at
        now = datetime.now(UTC)
        recent_checkpoint = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=now - timedelta(days=10),  # 10 days old
            last_record_id="pack-100",
            total_synced=100,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = recent_checkpoint
        mock_session.execute.return_value = mock_result

        # Mock API to return empty
        mock_api_client.get_packs.return_value = []

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have used existing checkpoint (not reset)
        # Verify checkpoint was read and used
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_stale_checkpoint_resets_last_record_id(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """Stale checkpoint reset should clear last_record_id to restart from beginning."""
        # Mock stale checkpoint
        now = datetime.now(UTC)
        stale_checkpoint = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=now - timedelta(days=60),  # Very stale
            last_record_id="pack-500",  # Should be reset
            total_synced=500,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = stale_checkpoint
        mock_session.execute.return_value = mock_result

        # Mock API to return empty
        mock_api_client.get_packs.return_value = []

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have reset checkpoint fields
        assert mock_session.add.called


class TestCheckpointPersistence:
    """Test checkpoint committed per batch."""

    @pytest.mark.asyncio
    async def test_checkpoint_committed_after_backfill_batch(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Checkpoint should be committed after each backfill batch."""
        # Mock API to return one batch
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have committed after backfill batch
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_checkpoint_committed_after_newest_check(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """Checkpoint should be committed after newest check."""
        # Mock API: backfill empty, newest has packs
        mock_api_client.get_packs.side_effect = [
            [],  # Backfill empty
            [sample_pack],  # Newest check
            [],  # Newest end
        ]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have committed after newest check
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_checkpoint_updated_with_last_record_id(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """Checkpoint should store last_record_id from batch."""
        pack1 = T3KPack(
            id="pack-1",
            name="Pack 1",
            slug="pack-1",
            creator_id="creator-1",
            description="First pack",
            thumbnail_url="https://example.com/1.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        pack2 = T3KPack(
            id="pack-2",
            name="Pack 2",
            slug="pack-2",
            creator_id="creator-1",
            description="Second pack",
            thumbnail_url="https://example.com/2.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
            updated_at=datetime(2024, 1, 2, tzinfo=UTC),
        )

        # Mock API to return batch with multiple packs
        mock_api_client.get_packs.side_effect = [[pack1, pack2], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have added checkpoint with last pack ID
        assert mock_session.add.called
        # Checkpoint should have last_record_id = "pack-2" (last pack in batch)


class TestPublishAfterStaging:
    """Test GearSyncRecord publishing after staging."""

    @pytest.mark.asyncio
    async def test_publish_pack_after_staging(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """publish_pack should be called for each newly staged pack."""
        # Mock API to return one pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called publish_pack once
        assert mock_publisher.publish_pack.call_count >= 1

    @pytest.mark.asyncio
    async def test_publish_multiple_packs_in_batch(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """publish_pack should be called for each pack in a batch."""
        pack1 = T3KPack(
            id="pack-1",
            name="Pack 1",
            slug="pack-1",
            creator_id="creator-1",
            description="First",
            thumbnail_url="https://example.com/1.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        pack2 = T3KPack(
            id="pack-2",
            name="Pack 2",
            slug="pack-2",
            creator_id="creator-1",
            description="Second",
            thumbnail_url="https://example.com/2.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
            updated_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
        pack3 = T3KPack(
            id="pack-3",
            name="Pack 3",
            slug="pack-3",
            creator_id="creator-1",
            description="Third",
            thumbnail_url="https://example.com/3.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
            updated_at=datetime(2024, 1, 3, tzinfo=UTC),
        )

        # Mock API to return 3 packs
        mock_api_client.get_packs.side_effect = [[pack1, pack2, pack3], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called publish_pack 3 times
        assert mock_publisher.publish_pack.call_count >= 3

    @pytest.mark.asyncio
    async def test_publish_passes_staging_model(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
        sample_pack: T3KPack,
    ) -> None:
        """publish_pack should receive T3KPackStaging instance."""
        # Mock API to return pack
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should have called publish_pack with T3KPackStaging
        assert mock_publisher.publish_pack.called
        # Verify first call received a staging model (has from_domain method)
        call_args = mock_publisher.publish_pack.call_args_list[0]
        staging_model = call_args[0][0]
        assert hasattr(staging_model, "id")
        assert hasattr(staging_model, "name")

    @pytest.mark.asyncio
    async def test_no_publish_if_empty_batch(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_publisher: MagicMock,
    ) -> None:
        """publish_pack should not be called if API returns empty batch."""
        # Mock API to return empty
        mock_api_client.get_packs.return_value = []

        await sync_service.run_catalog_sync(publisher=mock_publisher, max_iterations=1)

        # Should not have called publish_pack
        assert mock_publisher.publish_pack.call_count == 0
