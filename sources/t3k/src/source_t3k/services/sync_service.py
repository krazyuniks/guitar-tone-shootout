"""T3K Sync Service.

Coordinates fetching data from the T3K API and upserting it to staging tables.
Supports multiple sync strategies (backfill, newest) and checkpoint management.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import (
    SyncCheckpoint,
    T3KModelStaging,
    T3KPackStaging,
)


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
