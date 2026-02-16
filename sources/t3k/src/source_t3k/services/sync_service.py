"""T3K Sync Service.

Coordinates fetching data from the T3K API and upserting it to staging tables.
Supports multiple sync strategies (backfill, newest) and checkpoint management.
"""

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import (
    SyncCheckpoint,
    T3KModelStaging,
    T3KToneStaging,
)
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.services.model_downloader import ModelDownloader

logger = logging.getLogger(__name__)


class T3KSyncService:
    """T3K synchronisation service.

    Coordinates fetching data from the T3K API and upserting it to staging tables.
    Manages checkpoints for resumable syncs and progress tracking.
    """

    def __init__(
        self,
        api_client: T3KAPIClient,
        session: AsyncSession,
        model_downloader: ModelDownloader | None = None,
    ) -> None:
        self._api_client = api_client
        self._session = session
        self._model_downloader = model_downloader

    async def run_catalog_sync(
        self, publisher: GearSyncPublisher, max_iterations: int | None = None
    ) -> None:
        """Run interleaved backfill and newest sync loop.

        Alternates between backfill (walking oldest→newest from checkpoint) and
        newest (checking for recent updates). Each iteration consists of one backfill
        batch followed by one newest check.
        """
        pairs_completed = 0

        while max_iterations is None or pairs_completed < max_iterations:
            checkpoint = await self._read_checkpoint_with_aliases(entity_type="tone")

            # Reset stale checkpoints (older than 30 days)
            now = datetime.now(UTC)
            if checkpoint is not None and isinstance(checkpoint.last_synced_at, datetime):
                age = now - checkpoint.last_synced_at
                if age > timedelta(days=30):
                    checkpoint.last_record_id = ""
                    checkpoint.last_synced_at = now
                    self._session.add(checkpoint)
                    await self._session.commit()

            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_backfill_batch(checkpoint, publisher)

            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_newest_check(checkpoint, publisher)

            pairs_completed += 1

    async def _read_checkpoint_with_aliases(self, entity_type: str) -> SyncCheckpoint | None:
        """Read a checkpoint supporting singular/plural aliases."""
        candidates = [entity_type]
        if entity_type.endswith("s"):
            candidates.append(entity_type[:-1])
        else:
            candidates.append(f"{entity_type}s")

        for candidate in candidates:
            checkpoint = await self._read_checkpoint(source_name="t3k", entity_type=candidate)
            if checkpoint is not None:
                return checkpoint
        return None

    async def _read_checkpoint(self, source_name: str, entity_type: str) -> SyncCheckpoint | None:
        stmt = select(SyncCheckpoint).where(
            SyncCheckpoint.source_name == source_name,
            SyncCheckpoint.entity_type == entity_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_checkpoint(
        self, entity_type: str, last_record_id: str, increment: int
    ) -> SyncCheckpoint:
        """Create or update sync checkpoint in the current transaction."""
        now = datetime.now(UTC)
        checkpoint = await self._read_checkpoint_with_aliases(entity_type=entity_type)
        if checkpoint is None:
            checkpoint = SyncCheckpoint(
                source_name="t3k",
                entity_type=entity_type,
                last_synced_at=now,
                last_record_id=last_record_id,
                total_synced=max(0, increment),
            )
        else:
            checkpoint.last_synced_at = now
            checkpoint.last_record_id = last_record_id
            checkpoint.total_synced = checkpoint.total_synced + max(0, increment)

        self._session.add(checkpoint)
        return checkpoint

    async def _stage_tone_models_and_publish(
        self,
        tone: Any,
        publisher: GearSyncPublisher,
    ) -> bool:
        """Stage a tone + all models and publish one aggregate sync record.

        Returns True if staged/published, False if skipped.
        """
        staging_tone = T3KToneStaging.from_domain(tone)
        staging_tone.last_synced_at = datetime.now(UTC)
        self._session.add(staging_tone)

        # Fetch and stage models for this tone.
        models = await self._api_client.get_models(tone.id)
        staging_models: list[T3KModelStaging] = []
        for model in models:
            staging_model = T3KModelStaging.from_domain(model)
            self._session.add(staging_model)
            staging_models.append(staging_model)

        if not staging_models:
            logger.warning("Skipping tone %s because it has no models", tone.id)
            return False

        # Download model files before publishing (non-fatal)
        if self._model_downloader is not None:
            try:
                await self._session.flush()
                await self._model_downloader.download_models_for_tone(tone.id)
            except Exception as e:
                logger.warning(
                    "Download failed for tone %s (will publish anyway): %s",
                    tone.id,
                    str(e),
                )

        await self._upsert_checkpoint(
            entity_type="model",
            last_record_id=str(staging_models[-1].id),
            increment=len(staging_models),
        )

        await publisher.publish_tone(staging_tone, models=staging_models)
        return True

    async def _run_backfill_batch(
        self, checkpoint: SyncCheckpoint | None, publisher: GearSyncPublisher
    ) -> None:
        """Run a single backfill batch."""
        page = 1
        page_size = 100
        total_synced = checkpoint.total_synced if checkpoint else 0
        last_result_id: int | None = None

        while True:
            tones = await self._api_client.get_tones(page=page, page_size=page_size)

            if not tones:
                break

            # Infinite loop protection
            current_result_id = id(tones)
            if last_result_id is not None and current_result_id == last_result_id:
                break
            last_result_id = current_result_id

            processed_tones = 0
            for tone in tones:
                existing = await self._get_existing_tone(tone.id)
                if (
                    existing is not None
                    and existing.last_synced_at is not None
                    and isinstance(existing.last_synced_at, datetime)
                ):
                    age = datetime.now(UTC) - existing.last_synced_at
                    if age <= timedelta(days=7):
                        continue

                published = await self._stage_tone_models_and_publish(tone, publisher)
                if published:
                    processed_tones += 1

            total_synced += processed_tones
            last_record_id = str(tones[-1].id) if tones else ""
            checkpoint = await self._upsert_checkpoint(
                entity_type="tone",
                last_record_id=last_record_id,
                increment=processed_tones,
            )
            checkpoint.total_synced = total_synced
            await self._session.commit()

            page += 1

    async def _run_newest_check(
        self, checkpoint: SyncCheckpoint | None, publisher: GearSyncPublisher
    ) -> None:
        """Run a newest check batch."""
        page = 1
        page_size = 100
        max_pages = 2
        total_synced = checkpoint.total_synced if checkpoint else 0
        should_stop = False

        for _ in range(max_pages):
            if should_stop:
                break

            tones = await self._api_client.get_tones(page=page, page_size=page_size)

            if not tones:
                break

            any_processed = False
            processed_tones = 0
            for tone in tones:
                existing = await self._get_existing_tone(tone.id)
                if existing is not None:
                    should_stop = True
                    break

                published = await self._stage_tone_models_and_publish(tone, publisher)
                any_processed = any_processed or published
                if published:
                    processed_tones += 1

            if any_processed:
                total_synced += processed_tones
                last_record_id = str(tones[-1].id) if tones else ""
                checkpoint = await self._upsert_checkpoint(
                    entity_type="tone",
                    last_record_id=last_record_id,
                    increment=processed_tones,
                )
                checkpoint.total_synced = total_synced
                await self._session.commit()

            page += 1

    async def _get_existing_tone(self, tone_id: int) -> T3KToneStaging | None:
        stmt = select(T3KToneStaging).where(T3KToneStaging.id == tone_id)
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        if value is not None and not isinstance(value, T3KToneStaging):
            return None
        return value
