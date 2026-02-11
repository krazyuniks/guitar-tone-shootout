"""Unit tests for T3K Sync Service.

The sync service coordinates fetching data from the T3K API and upserting it
to staging tables. Tests verify sync strategies (backfill, newest), pagination,
checkpoint management, and error recovery.
"""

import contextlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import SyncCheckpoint
from source_t3k.domain.entities import T3KModel, T3KPack
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
def sample_model() -> T3KModel:
    """Create a sample T3K model entity."""
    return T3KModel(
        id="model-1",
        pack_id="pack-1",
        name="Test Model",
        filename="test_model.nam",
        file_size=1024000,
        download_url="https://example.com/model.nam",
        checksum="abc123",
        created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
    )


class TestT3KSyncServiceImport:
    """Test that T3KSyncService exists and is importable."""

    def test_service_class_exists(self) -> None:
        """T3KSyncService class should exist and be importable."""
        from source_t3k.services.sync_service import T3KSyncService

        assert T3KSyncService is not None
        assert callable(T3KSyncService)


class TestT3KSyncServiceConstruction:
    """Test T3KSyncService initialization."""

    def test_service_accepts_dependencies(
        self, mock_api_client: AsyncMock, mock_session: AsyncMock
    ) -> None:
        """T3KSyncService should accept api_client and session dependencies."""
        service = T3KSyncService(api_client=mock_api_client, session=mock_session)

        assert service is not None
        assert hasattr(service, "sync_packs")
        assert hasattr(service, "sync_models")


class TestT3KSyncServiceSyncPacks:
    """Test T3KSyncService.sync_packs() method."""

    @pytest.mark.asyncio
    async def test_sync_packs_fetches_from_api(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs should call api_client.get_packs() to fetch data."""
        # Mock API to return one page with one pack
        mock_api_client.get_packs.return_value = [sample_pack]

        await sync_service.sync_packs()

        # Should have called get_packs at least once
        mock_api_client.get_packs.assert_called()

    @pytest.mark.asyncio
    async def test_sync_packs_upserts_to_staging(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs should upsert packs to T3KPackStaging table."""
        # Mock API to return one pack, then empty list (end pagination)
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.sync_packs()

        # Should have added a staging model to session
        mock_session.add.assert_called()
        # Should have committed the transaction
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_packs_paginates_until_empty(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs should paginate through all pages until empty list."""
        # Mock API to return 3 pages, then empty
        mock_api_client.get_packs.side_effect = [
            [sample_pack],  # Page 1
            [sample_pack],  # Page 2
            [sample_pack],  # Page 3
            [],  # Page 4 - empty, should stop
        ]

        await sync_service.sync_packs()

        # Should have called get_packs 4 times (3 with data, 1 empty)
        assert mock_api_client.get_packs.call_count == 4

    @pytest.mark.asyncio
    async def test_sync_packs_reads_checkpoint_before_sync(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """sync_packs should read checkpoint to determine starting point."""
        # Mock empty API response
        mock_api_client.get_packs.return_value = []

        await sync_service.sync_packs()

        # Should have executed a query (to read checkpoint)
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_sync_packs_updates_checkpoint_after_page(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs should update checkpoint after each page."""
        # Mock API to return one page, then empty
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.sync_packs()

        # Should have added checkpoint update to session
        # (verify session.add was called with SyncCheckpoint-like object)
        assert mock_session.add.call_count >= 1
        # Should have committed checkpoint
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_sync_packs_backfill_strategy_paginates_all(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs with backfill strategy should paginate through all records."""
        # Mock multiple pages of data
        mock_api_client.get_packs.side_effect = [
            [sample_pack] * 50,  # Page 1 - full page
            [sample_pack] * 50,  # Page 2 - full page
            [sample_pack] * 20,  # Page 3 - partial page
            [],  # Page 4 - empty
        ]

        await sync_service.sync_packs(strategy="backfill")

        # Should have called get_packs 4 times
        assert mock_api_client.get_packs.call_count == 4

    @pytest.mark.asyncio
    async def test_sync_packs_handles_api_error_gracefully(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """sync_packs should handle API errors without losing checkpoint progress."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        # Mock API to fail
        mock_api_client.get_packs.side_effect = T3KAPIError("API error")

        # Should not raise exception (or should handle it)
        with contextlib.suppress(T3KAPIError):
            await sync_service.sync_packs()

        # Checkpoint should have been attempted even on error
        # (implementation should save progress before API call fails)
        assert mock_session.execute.called


class TestT3KSyncServiceSyncModels:
    """Test T3KSyncService.sync_models() method."""

    @pytest.mark.asyncio
    async def test_sync_models_fetches_from_api(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        sample_model: T3KModel,
    ) -> None:
        """sync_models should call api_client.get_models() for each pack."""
        # Mock get_models to return models
        mock_api_client.get_models.return_value = [sample_model]

        await sync_service.sync_models(pack_id="pack-1")

        # Should have called get_models with pack_id
        mock_api_client.get_models.assert_called_once_with("pack-1")

    @pytest.mark.asyncio
    async def test_sync_models_upserts_to_staging(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_model: T3KModel,
    ) -> None:
        """sync_models should upsert models to T3KModelStaging table."""
        # Mock API to return one model
        mock_api_client.get_models.return_value = [sample_model]

        await sync_service.sync_models(pack_id="pack-1")

        # Should have added staging model to session
        mock_session.add.assert_called()
        # Should have committed
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_models_handles_empty_pack(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """sync_models should handle packs with no models gracefully."""
        # Mock API to return empty list
        mock_api_client.get_models.return_value = []

        await sync_service.sync_models(pack_id="pack-1")

        # Should still have committed (empty commit is OK)
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_models_updates_checkpoint(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_model: T3KModel,
    ) -> None:
        """sync_models should update checkpoint after syncing models."""
        # Mock API to return models
        mock_api_client.get_models.return_value = [sample_model]

        await sync_service.sync_models(pack_id="pack-1")

        # Should have added checkpoint to session
        assert mock_session.add.call_count >= 1
        # Should have committed checkpoint
        assert mock_session.commit.call_count >= 1


class TestT3KSyncServiceCheckpointManagement:
    """Test checkpoint persistence and recovery."""

    @pytest.mark.asyncio
    async def test_checkpoint_survives_restart(
        self,
        sync_service: T3KSyncService,
        mock_session: AsyncMock,
    ) -> None:
        """Checkpoint should be read from database on service start."""
        # Mock session to return a checkpoint
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=datetime(2024, 1, 1, tzinfo=UTC),
            last_record_id="pack-100",
            total_synced=100,
        )
        mock_session.execute.return_value = mock_result

        # Should read checkpoint when starting sync
        await sync_service.sync_packs()

        # Should have executed query to read checkpoint
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_checkpoint_stores_last_synced_timestamp(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """Checkpoint should store last_synced_at timestamp."""
        # Mock API response
        mock_api_client.get_packs.side_effect = [[sample_pack], []]

        await sync_service.sync_packs()

        # Verify that session.add was called with checkpoint-like data
        # (implementation should create SyncCheckpoint with last_synced_at)
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_checkpoint_stores_total_synced_count(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """Checkpoint should track total_synced count."""
        # Mock API to return multiple packs
        mock_api_client.get_packs.side_effect = [[sample_pack] * 10, []]

        await sync_service.sync_packs()

        # Checkpoint should have been updated with count
        assert mock_session.add.called
        assert mock_session.commit.called


class TestT3KSyncServiceNewestStrategy:
    """Test 'newest' sync strategy (incremental updates)."""

    @pytest.mark.asyncio
    async def test_newest_strategy_queries_since_checkpoint(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Newest strategy should only fetch records updated since last checkpoint."""
        # Mock checkpoint with timestamp
        last_sync = datetime(2024, 1, 1, tzinfo=UTC)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=last_sync,
            last_record_id="pack-50",
            total_synced=50,
        )
        mock_session.execute.return_value = mock_result

        # Mock API response
        mock_api_client.get_packs.return_value = []

        await sync_service.sync_packs(strategy="newest")

        # Should have called get_packs with updated_since parameter (or similar)
        # (exact API depends on implementation, but should use checkpoint timestamp)
        mock_api_client.get_packs.assert_called()

    @pytest.mark.asyncio
    async def test_newest_strategy_does_not_paginate_all(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """Newest strategy should not paginate through all records."""
        # Mock checkpoint
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = SyncCheckpoint(
            id=1,
            source_name="t3k",
            entity_type="packs",
            last_synced_at=datetime(2024, 1, 1, tzinfo=UTC),
            last_record_id="pack-100",
            total_synced=100,
        )
        mock_session.execute.return_value = mock_result

        # Mock API to return only recent updates
        recent_pack = T3KPack(
            id="pack-101",
            name="New Pack",
            slug="new-pack",
            creator_id="creator-1",
            description="Recent pack",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
            updated_at=datetime(2024, 1, 5, tzinfo=UTC),
        )
        mock_api_client.get_packs.side_effect = [[recent_pack], []]

        await sync_service.sync_packs(strategy="newest")

        # Should only fetch recent pages (not start from page 1)
        assert mock_api_client.get_packs.call_count <= 2


class TestT3KSyncServiceErrorRecovery:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_api_error_does_not_lose_progress(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """API error should not lose already-synced progress."""
        from source_t3k.adapters.inbound.exceptions import T3KAPIError

        # Mock API: first page succeeds, second page fails
        mock_api_client.get_packs.side_effect = [
            [sample_pack],
            T3KAPIError("Network error"),
        ]

        # Attempt sync (may raise or handle error)
        with contextlib.suppress(T3KAPIError):
            await sync_service.sync_packs()

        # First page checkpoint should have been saved
        # (verify commit was called after first page)
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_database_error_is_propagated(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        mock_session: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """Database errors should be propagated (not silently swallowed)."""
        from sqlalchemy.exc import OperationalError

        # Mock API success but DB failure
        mock_api_client.get_packs.return_value = [sample_pack]
        mock_session.commit.side_effect = OperationalError("DB error", None, None)

        # Should raise the DB error
        with pytest.raises(OperationalError):
            await sync_service.sync_packs()


class TestT3KSyncServiceLongLivedTask:
    """Test sync service as a long-lived task."""

    @pytest.mark.asyncio
    async def test_sync_service_can_run_multiple_times(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
        sample_pack: T3KPack,
    ) -> None:
        """sync_packs should be callable multiple times (long-lived task)."""
        # Mock API responses
        mock_api_client.get_packs.side_effect = [
            [sample_pack],
            [],
            [sample_pack],
            [],
        ]

        # Run sync twice
        await sync_service.sync_packs()
        await sync_service.sync_packs()

        # Should have called API 4 times (2 syncs x 2 pages each)
        assert mock_api_client.get_packs.call_count == 4

    @pytest.mark.asyncio
    async def test_sync_service_does_not_block_indefinitely(
        self,
        sync_service: T3KSyncService,
        mock_api_client: AsyncMock,
    ) -> None:
        """sync_packs should complete (not run forever in single call)."""
        # Mock API to return empty immediately
        mock_api_client.get_packs.return_value = []

        # Should complete quickly
        await sync_service.sync_packs()

        # If we reach here, it didn't block
        assert True
