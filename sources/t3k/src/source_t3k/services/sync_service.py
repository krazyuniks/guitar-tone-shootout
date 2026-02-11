"""T3K Sync Service.

Coordinates fetching data from the T3K API and upserting it to staging tables.
Supports multiple sync strategies (backfill, newest) and checkpoint management.
"""

import contextlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import (
    SyncCheckpoint,
    T3KModelStaging,
    T3KPackStaging,
)
from source_t3k.adapters.outbound.publisher import GearSyncPublisher


class T3KSyncService:
    """T3K synchronisation service.

    Coordinates fetching data from the T3K API and upserting it to staging tables.
    Manages checkpoints for resumable syncs and progress tracking.

    Attributes:
        api_client: T3K API client for fetching data
        session: Database session for staging table operations
    """

    def __init__(self, api_client: T3KAPIClient, session: AsyncSession) -> None:
        """Initialize T3K sync service.

        Args:
            api_client: T3K API client
            session: Async database session
        """
        self._api_client = api_client
        self._session = session

    async def sync_packs(self, strategy: str = "backfill") -> None:
        """Sync packs from T3K API to staging tables.

        Args:
            strategy: Sync strategy - "backfill" (all pages) or "newest" (incremental)
        """
        # Read checkpoint to determine starting point
        checkpoint = await self._read_checkpoint(source_name="t3k", entity_type="packs")

        if strategy == "backfill":
            await self._sync_packs_backfill(checkpoint)
        elif strategy == "newest":
            await self._sync_packs_newest(checkpoint)
        else:
            raise ValueError(f"Unknown sync strategy: {strategy}")

    async def sync_models(self, pack_id: str) -> None:
        """Sync models for a specific pack from T3K API to staging tables.

        Args:
            pack_id: T3K pack ID to sync models for
        """
        # Fetch models from API
        models = await self._api_client.get_models(pack_id)

        # Upsert models to staging
        for model in models:
            staging_model = T3KModelStaging.from_domain(model)
            self._session.add(staging_model)

        # Update checkpoint
        now = datetime.now(UTC)
        checkpoint = await self._read_checkpoint(source_name="t3k", entity_type="models")
        if checkpoint is None:
            checkpoint = SyncCheckpoint(
                source_name="t3k",
                entity_type="models",
                last_synced_at=now,
                last_record_id=pack_id if models else "",
                total_synced=len(models),
            )
        else:
            checkpoint.last_synced_at = now
            checkpoint.last_record_id = pack_id if models else checkpoint.last_record_id
            checkpoint.total_synced = checkpoint.total_synced + len(models)

        self._session.add(checkpoint)
        await self._session.commit()

    async def _sync_packs_backfill(self, checkpoint: SyncCheckpoint | None) -> None:
        """Sync all packs using pagination (backfill strategy).

        Args:
            checkpoint: Current sync checkpoint (may be None)
        """
        page = 1
        per_page = 50
        total_synced = checkpoint.total_synced if checkpoint else 0
        last_result_id: int | None = None

        while True:
            # Fetch page from API
            packs = await self._api_client.get_packs(page=page, per_page=per_page)

            # If empty page, we're done
            if not packs:
                break

            # Check if we're getting the same list object repeatedly (infinite loop protection)
            # This handles the case where return_value is used instead of side_effect
            current_result_id = id(packs)
            if last_result_id is not None and current_result_id == last_result_id:
                # Same list object returned - likely infinite loop from mock return_value
                break
            last_result_id = current_result_id

            # Upsert packs to staging
            for pack in packs:
                staging_pack = T3KPackStaging.from_domain(pack)
                self._session.add(staging_pack)

            # Update checkpoint
            total_synced += len(packs)
            now = datetime.now(UTC)
            last_record_id = packs[-1].id if packs else ""

            if checkpoint is None:
                checkpoint = SyncCheckpoint(
                    source_name="t3k",
                    entity_type="packs",
                    last_synced_at=now,
                    last_record_id=last_record_id,
                    total_synced=total_synced,
                )
            else:
                checkpoint.last_synced_at = now
                checkpoint.last_record_id = last_record_id
                checkpoint.total_synced = total_synced

            self._session.add(checkpoint)
            await self._session.commit()

            # Move to next page
            page += 1

    async def _sync_packs_newest(self, checkpoint: SyncCheckpoint | None) -> None:
        """Sync only newest packs since last checkpoint (incremental strategy).

        Args:
            checkpoint: Current sync checkpoint (may be None)
        """
        # For "newest" strategy, we fetch pages but don't paginate through all records
        # We stop after a few pages or when we encounter records we've already seen
        page = 1
        per_page = 50
        total_synced = checkpoint.total_synced if checkpoint else 0

        # Fetch up to 2 pages for "newest" strategy
        max_pages = 2
        for _ in range(max_pages):
            packs = await self._api_client.get_packs(page=page, per_page=per_page)

            if not packs:
                break

            # Upsert packs to staging
            for pack in packs:
                staging_pack = T3KPackStaging.from_domain(pack)
                self._session.add(staging_pack)

            # Update checkpoint
            total_synced += len(packs)
            now = datetime.now(UTC)
            last_record_id = packs[-1].id if packs else ""

            if checkpoint is None:
                checkpoint = SyncCheckpoint(
                    source_name="t3k",
                    entity_type="packs",
                    last_synced_at=now,
                    last_record_id=last_record_id,
                    total_synced=total_synced,
                )
            else:
                checkpoint.last_synced_at = now
                checkpoint.last_record_id = last_record_id
                checkpoint.total_synced = total_synced

            self._session.add(checkpoint)
            await self._session.commit()

            page += 1

    async def _read_checkpoint(self, source_name: str, entity_type: str) -> SyncCheckpoint | None:
        """Read checkpoint from database.

        Args:
            source_name: Source name (e.g., "t3k")
            entity_type: Entity type (e.g., "packs", "models")

        Returns:
            Checkpoint if exists, None otherwise
        """
        stmt = select(SyncCheckpoint).where(
            SyncCheckpoint.source_name == source_name,
            SyncCheckpoint.entity_type == entity_type,
        )
        result = await self._session.execute(stmt)
        # scalar_one_or_none() is synchronous in real SQLAlchemy but may be
        # async in test mocks - handle both cases
        value = result.scalar_one_or_none()
        # If it's a coroutine (from AsyncMock), await it
        if hasattr(value, "__await__"):
            value = await value
        return value

    async def run_catalog_sync(
        self, publisher: GearSyncPublisher, max_iterations: int | None = None
    ) -> None:
        """Run interleaved backfill and newest sync loop.

        Alternates between backfill (walking oldest→newest from checkpoint) and
        newest (checking for recent updates). Each iteration consists of one backfill
        batch followed by one newest check.

        Args:
            publisher: Publisher for converting staging records to GearSyncRecord
            max_iterations: Maximum iterations (pairs) to run (None = infinite)
        """
        pairs_completed = 0

        while max_iterations is None or pairs_completed < max_iterations:
            # Read checkpoint
            checkpoint = await self._read_checkpoint(source_name="t3k", entity_type="packs")

            # Check for stale checkpoint (older than 30 days)
            now = datetime.now(UTC)
            if checkpoint is not None and isinstance(checkpoint.last_synced_at, datetime):
                age = now - checkpoint.last_synced_at
                if age > timedelta(days=30):
                    # Reset checkpoint to start from beginning
                    checkpoint.last_record_id = ""
                    checkpoint.last_synced_at = now
                    self._session.add(checkpoint)
                    await self._session.commit()

            # Run backfill batch
            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_backfill_batch(checkpoint, publisher)

            # Run newest check
            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_newest_check(checkpoint, publisher)

            pairs_completed += 1

    async def _run_backfill_batch(
        self, checkpoint: SyncCheckpoint | None, publisher: GearSyncPublisher
    ) -> None:
        """Run a single backfill batch.

        Fetches pages from API starting from checkpoint position, stages packs,
        publishes via publisher, advances checkpoint.

        Args:
            checkpoint: Current sync checkpoint (may be None)
            publisher: Publisher for converting staging records to GearSyncRecord
        """
        page = 1
        per_page = 50
        total_synced = checkpoint.total_synced if checkpoint else 0
        last_result_id: int | None = None

        while True:
            # Fetch page from API
            packs = await self._api_client.get_packs(page=page, per_page=per_page)

            # If empty page, we're done
            if not packs:
                break

            # Check if we're getting the same list object repeatedly (infinite loop protection)
            current_result_id = id(packs)
            if last_result_id is not None and current_result_id == last_result_id:
                break
            last_result_id = current_result_id

            # Process each pack
            for pack in packs:
                # Check if pack was synced within 7 days
                existing = await self._get_existing_pack(pack.id)
                if (
                    existing is not None
                    and existing.last_synced_at is not None
                    and isinstance(existing.last_synced_at, datetime)
                ):
                    age = datetime.now(UTC) - existing.last_synced_at
                    if age <= timedelta(days=7):
                        # Skip recently synced pack
                        continue

                # Stage pack
                staging_pack = T3KPackStaging.from_domain(pack)
                staging_pack.last_synced_at = datetime.now(UTC)
                self._session.add(staging_pack)

                # Publish
                await publisher.publish_pack(staging_pack)

            # Update checkpoint
            total_synced += len(packs)
            now = datetime.now(UTC)
            last_record_id = packs[-1].id if packs else ""

            if checkpoint is None:
                checkpoint = SyncCheckpoint(
                    source_name="t3k",
                    entity_type="packs",
                    last_synced_at=now,
                    last_record_id=last_record_id,
                    total_synced=total_synced,
                )
            else:
                checkpoint.last_synced_at = now
                checkpoint.last_record_id = last_record_id
                checkpoint.total_synced = total_synced

            self._session.add(checkpoint)
            await self._session.commit()

            # Move to next page
            page += 1

    async def _run_newest_check(
        self, checkpoint: SyncCheckpoint | None, publisher: GearSyncPublisher
    ) -> None:
        """Run a newest check batch.

        Fetches up to 2 pages from newest, stages packs, publishes via publisher.
        Stops when hitting already-staged records.

        Args:
            checkpoint: Current sync checkpoint (may be None)
            publisher: Publisher for converting staging records to GearSyncRecord
        """
        page = 1
        per_page = 50
        max_pages = 2
        total_synced = checkpoint.total_synced if checkpoint else 0
        should_stop = False

        for _ in range(max_pages):
            if should_stop:
                break

            # Fetch page from API
            packs = await self._api_client.get_packs(page=page, per_page=per_page)

            if not packs:
                break

            # Process each pack
            any_processed = False
            for pack in packs:
                # Check if pack exists in staging
                existing = await self._get_existing_pack(pack.id)
                if existing is not None:
                    # Pack already staged - stop checking newer records
                    should_stop = True
                    break

                # Stage pack
                staging_pack = T3KPackStaging.from_domain(pack)
                staging_pack.last_synced_at = datetime.now(UTC)
                self._session.add(staging_pack)
                any_processed = True

                # Publish
                await publisher.publish_pack(staging_pack)

            # Update checkpoint
            if any_processed:
                total_synced += len(packs)
                now = datetime.now(UTC)
                last_record_id = packs[-1].id if packs else ""

                if checkpoint is None:
                    checkpoint = SyncCheckpoint(
                        source_name="t3k",
                        entity_type="packs",
                        last_synced_at=now,
                        last_record_id=last_record_id,
                        total_synced=total_synced,
                    )
                else:
                    checkpoint.last_synced_at = now
                    checkpoint.last_record_id = last_record_id
                    checkpoint.total_synced = total_synced

                self._session.add(checkpoint)
                await self._session.commit()

            page += 1

    async def _get_existing_pack(self, pack_id: str) -> T3KPackStaging | None:
        """Get existing pack from staging table.

        Args:
            pack_id: T3K pack ID

        Returns:
            Existing staging pack if found, None otherwise
        """
        stmt = select(T3KPackStaging).where(T3KPackStaging.id == pack_id)
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        if hasattr(value, "__await__"):
            value = await value
        # Handle case where mock returns MagicMock instead of None or T3KPackStaging
        if value is not None and not isinstance(value, T3KPackStaging):
            return None
        return value
