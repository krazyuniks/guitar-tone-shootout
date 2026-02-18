"""T3K Sync Service.

Coordinates fetching data from the T3K API and upserting it to staging tables.
Uses a dual-sync strategy: newest-first (stay current) + oldest-first backfill
(fill gaps). Newest check is the priority path — fast, self-terminating.
Backfill walks the catalogue from oldest to newest, resuming from checkpoint.
"""

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
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

BACKFILL_CHECKPOINT_TYPE = "backfill_page"


class T3KSyncService:
    """T3K synchronisation service.

    Coordinates fetching data from the T3K API and upserting it to staging tables.
    Uses a dual-sync strategy:
    - Newest check: walks sort=newest from page 1, stops at first known tone
    - Backfill: walks sort=oldest from checkpoint page, fills gaps
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
        """Run interleaved newest + backfill sync loop.

        Each iteration: newest check first (fast — usually 0-1 pages),
        then one backfill page (slow — 1 page + N model fetches).
        """
        pairs_completed = 0

        while max_iterations is None or pairs_completed < max_iterations:
            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_newest_check(publisher)

            with contextlib.suppress(StopIteration, StopAsyncIteration):
                await self._run_backfill_batch(publisher)

            pairs_completed += 1

    # ── Checkpoint management ────────────────────────────────────────────

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

    # ── Staging helpers ──────────────────────────────────────────────────

    async def _upsert_model(self, model: Any) -> T3KModelStaging:
        """Upsert a model to staging, preserving file_synced_at."""
        existing = await self._session.get(T3KModelStaging, model.id)
        if existing is not None:
            existing.tone_id = model.tone_id
            existing.user_id = model.user_id
            existing.name = model.name
            existing.model_url = model.model_url
            existing.size = model.size
            existing.created_at = model.created_at
            existing.updated_at = model.updated_at
            return existing
        staging = T3KModelStaging.from_domain(model)
        self._session.add(staging)
        return staging

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
        await self._session.merge(staging_tone)

        # Fetch and stage models for this tone.
        models = await self._api_client.get_models(tone.id)
        staging_models: list[T3KModelStaging] = []
        for model in models:
            staging_model = await self._upsert_model(model)
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

    async def _stage_models_only(
        self,
        tone_id: int,
        publisher: GearSyncPublisher,
        existing_tone: T3KToneStaging,
    ) -> bool:
        """Fetch and stage only models for a tone that already exists in staging.

        Used by backfill when a tone exists but is missing some models.
        Returns True if new models were staged/published.
        """
        models = await self._api_client.get_models(tone_id)
        staging_models: list[T3KModelStaging] = []
        for model in models:
            staging_model = await self._upsert_model(model)
            staging_models.append(staging_model)

        if not staging_models:
            return False

        existing_tone.last_synced_at = datetime.now(UTC)
        self._session.add(existing_tone)

        if self._model_downloader is not None:
            try:
                await self._session.flush()
                await self._model_downloader.download_models_for_tone(tone_id)
            except Exception as e:
                logger.warning(
                    "Download failed for tone %s (will publish anyway): %s",
                    tone_id,
                    str(e),
                )

        await self._upsert_checkpoint(
            entity_type="model",
            last_record_id=str(staging_models[-1].id),
            increment=len(staging_models),
        )

        await publisher.publish_tone(existing_tone, models=staging_models)
        return True

    async def _get_existing_tone(self, tone_id: int) -> T3KToneStaging | None:
        stmt = select(T3KToneStaging).where(T3KToneStaging.id == tone_id)
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        if value is not None and not isinstance(value, T3KToneStaging):
            return None
        return value

    async def _count_staged_models(self, tone_id: int) -> int:
        """Count how many models are staged for a given tone."""
        stmt = select(func.count()).where(T3KModelStaging.tone_id == tone_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Newest check ─────────────────────────────────────────────────────

    async def _run_newest_check(self, publisher: GearSyncPublisher) -> None:
        """Walk sort=newest from page 1, stop at first known tone.

        This is the priority path — stays current. Self-terminating: no
        checkpoint needed because it always starts from the newest and stops
        when it reaches tones we already have.
        """
        page = 1
        page_size = 25

        while True:
            tones = await self._api_client.get_tones(page=page, page_size=page_size, sort="newest")

            if not tones:
                break

            processed_tones = 0
            hit_known = False
            for tone in tones:
                existing = await self._get_existing_tone(tone.id)
                if existing is not None:
                    hit_known = True
                    break

                published = await self._stage_tone_models_and_publish(tone, publisher)
                if published:
                    processed_tones += 1

            if processed_tones > 0:
                await self._upsert_checkpoint(
                    entity_type="tone",
                    last_record_id=str(tones[-1].id),
                    increment=processed_tones,
                )
                await self._session.commit()

            logger.info(
                "Newest check page %d: %d new tones%s",
                page,
                processed_tones,
                " (hit known tone, stopping)" if hit_known else "",
            )

            if hit_known:
                break

            page += 1

    # ── Backfill ─────────────────────────────────────────────────────────

    async def _run_backfill_batch(self, publisher: GearSyncPublisher) -> None:
        """Run one page of backfill using sort=oldest, resuming from checkpoint.

        Per-tone logic:
        1. Tone exists + all models staged → skip (no API call)
        2. Tone exists + missing models → fetch models only (1 API call)
        3. Tone doesn't exist → full sync (page already fetched tone, + get_models)

        After each page, updates checkpoint with current page number.
        When backfill reaches end of catalogue, resets to page 1.
        """
        backfill_cp = await self._read_checkpoint(
            source_name="t3k", entity_type=BACKFILL_CHECKPOINT_TYPE
        )
        page = int(backfill_cp.last_record_id) if backfill_cp else 1
        page_size = 25

        tones = await self._api_client.get_tones(page=page, page_size=page_size, sort="oldest")

        if not tones:
            # Reached end of catalogue — reset to page 1
            logger.info("Backfill reached end of catalogue at page %d, resetting to page 1", page)
            page = 1
            await self._upsert_backfill_checkpoint(page)
            await self._session.commit()
            return

        processed_tones = 0
        skipped_tones = 0
        for tone in tones:
            existing = await self._get_existing_tone(tone.id)

            if existing is not None:
                staged_count = await self._count_staged_models(tone.id)
                if staged_count >= existing.models_count:
                    # All models staged — skip entirely
                    skipped_tones += 1
                    continue

                # Missing models — fetch only models
                published = await self._stage_models_only(tone.id, publisher, existing)
                if published:
                    processed_tones += 1
            else:
                # New tone — full sync
                published = await self._stage_tone_models_and_publish(tone, publisher)
                if published:
                    processed_tones += 1

        # Update backfill checkpoint to next page
        next_page = page + 1
        await self._upsert_backfill_checkpoint(next_page)

        if processed_tones > 0:
            await self._upsert_checkpoint(
                entity_type="tone",
                last_record_id=str(tones[-1].id),
                increment=processed_tones,
            )

        await self._session.commit()

        logger.info(
            "Backfill page %d: %d processed, %d skipped (complete)",
            page,
            processed_tones,
            skipped_tones,
        )

    async def _upsert_backfill_checkpoint(self, page: int) -> None:
        """Update the backfill page checkpoint."""
        await self._upsert_checkpoint(
            entity_type=BACKFILL_CHECKPOINT_TYPE,
            last_record_id=str(page),
            increment=0,
        )
