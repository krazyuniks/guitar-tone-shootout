"""T3K Sync Service — continuous sync with per-tone error handling.

One public method: run_sync_batch(publisher, mode) → SyncBatchResult.
Loops internally: newest page first, then backfill pages until done.
Per-tone errors are caught and logged, never crash the batch.
Rate limiting is handled by the API client.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.outbound.models import (
    SyncCheckpoint,
    T3KModelStaging,
    T3KToneStaging,
)
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import SyncBatchResult, SyncMode, TonePackageResult
from source_t3k.services.api_call_tracker import get_tracker
from source_t3k.services.model_downloader import ModelDownloader

logger = logging.getLogger(__name__)

# T3K API page size limits (from https://www.tone3000.com/api)
TONES_PAGE_SIZE = 25  # /api/v1/tones/search max
MODELS_PAGE_SIZE = 100  # /api/v1/models max
USERS_PAGE_SIZE = 10  # /api/v1/users max

BACKFILL_CHECKPOINT_TYPE = "backfill_page"


class T3KSyncService:
    """T3K synchronisation service.

    Loops internally: newest page, then backfill pages.
    Rate limiting is handled by the API client (0.75 req/s).
    Per-tone errors are caught and logged — never crash the batch.
    """

    def __init__(
        self,
        api_client: T3KAPIClient,
        session: AsyncSession,
        model_downloader: ModelDownloader | None = None,
    ) -> None:
        self._api = api_client
        self._session = session
        self._downloader = model_downloader
        self._tracker = get_tracker()
        self._on_progress: Callable[[], Awaitable[None]] | None = None

    async def run_sync_batch(
        self,
        publisher: GearSyncPublisher,
        mode: SyncMode = SyncMode.BAU,
        on_progress: Callable[[], Awaitable[None]] | None = None,
    ) -> SyncBatchResult:
        """Run a full sync pass: newest page then backfill pages.

        In BAU mode, processes newest page first, then loops backfill
        pages until the end of the catalogue (or until all tones on a
        page are already complete).

        In CATCH_UP mode, processes newest page only (stops at first
        known tone).

        Args:
            on_progress: Optional async callback invoked after each tone,
                used by the job handler to renew the Redis lock.
        """
        self._on_progress = on_progress
        all_results: list[TonePackageResult] = []
        hit_known = False
        total_backfill_pages = 0

        # ── Newest page (always) ──────────────────────────────────
        newest_results, hit_known = await self._run_newest_page(publisher, mode)
        all_results.extend(newest_results)

        # ── Backfill loop (BAU only) ──────────────────────────────
        if mode == SyncMode.BAU:
            while True:
                page_results, reached_end = await self._run_one_backfill_page(publisher)
                all_results.extend(page_results)
                total_backfill_pages += 1

                if reached_end:
                    break

                # If every tone on this page was skipped, we're caught up
                if page_results and all(r.skipped for r in page_results):
                    break

        return self._build_result(
            mode,
            total_backfill_pages,
            all_results,
            hit_known=hit_known,
        )

    # ── Newest page ───────────────────────────────────────────────────────

    async def _run_newest_page(
        self, publisher: GearSyncPublisher, mode: SyncMode
    ) -> tuple[list[TonePackageResult], bool]:
        """Fetch one page of newest tones and process them.

        Returns (tone_results, hit_known).
        """
        tones = await self._api_get_tones(page=1, sort="newest")

        if not tones:
            return [], False

        tone_results: list[TonePackageResult] = []
        hit_known = False

        for tone in tones:
            try:
                existing = await self._get_existing_tone(tone.id)

                if existing is not None:
                    if mode == SyncMode.CATCH_UP:
                        tone_results.append(TonePackageResult(tone_id=tone.id, skipped=True))
                        hit_known = True
                        break

                    result = await self._process_existing_tone(tone, existing)
                    if result.skipped:
                        hit_known = True
                    tone_results.append(result)
                else:
                    result = await self._process_new_tone(tone)
                    tone_results.append(result)

                await self._session.commit()
                await self._publish_tone(publisher, tone.id)
                await self._notify_progress()
            except Exception as e:
                logger.error("Error processing tone %d on newest page: %s", tone.id, e)
                await self._session.rollback()
                tone_results.append(TonePackageResult(tone_id=tone.id, error=str(e)))

        return tone_results, hit_known

    # ── Backfill (one page) ───────────────────────────────────────────────

    async def _run_one_backfill_page(
        self, publisher: GearSyncPublisher
    ) -> tuple[list[TonePackageResult], bool]:
        """Fetch one backfill page and process it.

        Returns (tone_results, reached_end).
        """
        page = await self._read_backfill_page()
        tones = await self._api_get_tones(page=page, sort="oldest")

        if not tones:
            logger.info("Backfill reached end of catalogue at page %d, resetting to page 1", page)
            await self._upsert_backfill_checkpoint(1)
            await self._session.commit()
            return [], True

        tone_results: list[TonePackageResult] = []

        for tone in tones:
            try:
                existing = await self._get_existing_tone(tone.id)

                if existing is not None:
                    staged_count = await self._count_staged_models(tone.id)
                    if staged_count >= tone.models_count:
                        result = await self._download_missing_files(tone.id)
                        tone_results.append(
                            TonePackageResult(
                                tone_id=tone.id,
                                skipped=result.files_downloaded == 0,
                                files_downloaded=result.files_downloaded,
                            )
                        )
                    else:
                        result = await self._process_existing_tone(tone, existing)
                        tone_results.append(result)
                else:
                    result = await self._process_new_tone(tone)
                    tone_results.append(result)

                await self._session.commit()
                await self._publish_tone(publisher, tone.id)
                await self._notify_progress()
            except Exception as e:
                logger.error("Error processing tone %d on backfill page %d: %s", tone.id, page, e)
                await self._session.rollback()
                tone_results.append(TonePackageResult(tone_id=tone.id, error=str(e)))

        await self._upsert_backfill_checkpoint(page + 1)
        await self._session.commit()

        return tone_results, False

    # ── Per-tone processing ───────────────────────────────────────────────

    async def _process_new_tone(self, tone: Any) -> TonePackageResult:
        """Full sync for a tone not yet in staging."""
        api_calls = 0

        await self._upsert_tone(tone)

        models = await self._api_get_models(tone.id)
        api_calls += 1
        models_staged = 0
        for model in models:
            await self._upsert_model(model)
            models_staged += 1

        files_downloaded = 0
        if self._downloader is not None:
            staged_models = await self._get_staged_models(tone.id)
            for m in staged_models:
                if m.file_synced_at is not None:
                    continue
                dl_result = await self._try_download(m)
                if dl_result:
                    files_downloaded += 1

        return TonePackageResult(
            tone_id=tone.id,
            models_staged=models_staged,
            files_downloaded=files_downloaded,
            api_calls=api_calls,
        )

    async def _process_existing_tone(
        self, tone: Any, _existing: T3KToneStaging
    ) -> TonePackageResult:
        """Process an existing tone: check model counts, fetch if needed."""
        staged_count = await self._count_staged_models(tone.id)
        api_calls = 0
        models_staged = 0
        files_downloaded = 0

        if staged_count >= tone.models_count:
            dl_result = await self._download_missing_files(tone.id)
            if dl_result.files_downloaded > 0:
                return TonePackageResult(
                    tone_id=tone.id,
                    files_downloaded=dl_result.files_downloaded,
                )
            return TonePackageResult(tone_id=tone.id, skipped=True)

        # Models count mismatch — fetch all models
        models = await self._api_get_models(tone.id)
        api_calls += 1
        for model in models:
            await self._upsert_model(model)
            models_staged += 1

        await self._upsert_tone(tone)

        if self._downloader is not None:
            staged_models = await self._get_staged_models(tone.id)
            for m in staged_models:
                if m.file_synced_at is not None:
                    continue
                dl_result_single = await self._try_download(m)
                if dl_result_single:
                    files_downloaded += 1

        return TonePackageResult(
            tone_id=tone.id,
            models_staged=models_staged,
            files_downloaded=files_downloaded,
            api_calls=api_calls,
        )

    async def _notify_progress(self) -> None:
        """Call the on_progress callback if set (e.g., to renew a lock)."""
        if self._on_progress is not None:
            await self._on_progress()

    # ── Publishing ─────────────────────────────────────────────────────────

    async def _publish_tone(self, publisher: GearSyncPublisher, tone_id: int) -> None:
        """Publish a tone + models to pgmq. Errors are logged, not raised."""
        try:
            staging_tone = await self._get_existing_tone(tone_id)
            staged_models = await self._get_staged_models(tone_id)
            if staging_tone is not None and staged_models:
                await publisher.publish_tone(staging_tone, models=staged_models)
        except Exception as e:
            logger.warning("Failed to publish tone %d: %s", tone_id, e)

    # ── File downloads ────────────────────────────────────────────────────

    async def _download_missing_files(self, tone_id: int) -> TonePackageResult:
        """Check staged models for missing files and download them."""
        if self._downloader is None:
            return TonePackageResult(tone_id=tone_id)

        models = await self._get_staged_models(tone_id)
        files_downloaded = 0
        for m in models:
            if m.file_synced_at is not None:
                continue
            if await self._try_download(m):
                files_downloaded += 1

        return TonePackageResult(tone_id=tone_id, files_downloaded=files_downloaded)

    async def _try_download(self, model: T3KModelStaging) -> bool:
        """Try to download/mark a single model file. Returns True if file_synced_at was set."""
        if self._downloader is None:
            return False

        # Check if file already exists on disk
        path = self._downloader.get_model_path(model)
        if path.exists():
            model.file_synced_at = datetime.now(UTC)
            self._session.add(model)
            return True

        try:
            result = await self._downloader.download_model(model)
            if result is not None:
                model.file_synced_at = datetime.now(UTC)
                self._session.add(model)
                return True
        except Exception as e:
            logger.warning("Download failed for model %s: %s", model.id, e)

        return False

    # ── Upsert helpers ────────────────────────────────────────────────────

    async def _upsert_tone(self, tone: Any) -> None:
        """Upsert a tone to staging using INSERT ON CONFLICT."""
        values = {
            "id": tone.id,
            "title": tone.title,
            "description": tone.description,
            "tags": tone.tags,
            "makes": tone.makes,
            "gear": tone.gear.value if hasattr(tone.gear, "value") else tone.gear,
            "platform": tone.platform.value if hasattr(tone.platform, "value") else tone.platform,
            "models_count": tone.models_count,
            "favorites_count": tone.favorites_count,
            "downloads_count": tone.downloads_count,
            "images": tone.images,
            "user_id": tone.user_id,
            "url": tone.url,
            "created_at": tone.created_at,
            "updated_at": tone.updated_at,
            "last_synced_at": datetime.now(UTC),
        }
        update_cols = {k: v for k, v in values.items() if k != "id"}
        stmt = (
            pg_insert(T3KToneStaging)
            .values(**values)
            .on_conflict_do_update(index_elements=["id"], set_=update_cols)
        )
        await self._session.execute(stmt)

    async def _upsert_model(self, model: Any) -> None:
        """Upsert a model to staging, preserving file_synced_at."""
        values = {
            "id": model.id,
            "tone_id": model.tone_id,
            "user_id": model.user_id,
            "name": model.name,
            "model_url": model.model_url,
            "size": model.size,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
        update_cols = {k: v for k, v in values.items() if k != "id"}
        stmt = (
            pg_insert(T3KModelStaging)
            .values(**values)
            .on_conflict_do_update(index_elements=["id"], set_=update_cols)
        )
        await self._session.execute(stmt)

    async def _upsert_checkpoint(
        self, entity_type: str, last_record_id: str, increment: int
    ) -> None:
        """Upsert a sync checkpoint using INSERT ON CONFLICT."""
        now = datetime.now(UTC)
        values = {
            "source_name": "t3k",
            "entity_type": entity_type,
            "last_synced_at": now,
            "last_record_id": last_record_id,
            "total_synced": max(0, increment),
        }
        stmt = (
            pg_insert(SyncCheckpoint)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["source_name", "entity_type"],
                set_={
                    "last_synced_at": now,
                    "last_record_id": last_record_id,
                    "total_synced": SyncCheckpoint.total_synced + max(0, increment),
                },
            )
        )
        await self._session.execute(stmt)

    async def _upsert_backfill_checkpoint(self, page: int) -> None:
        """Update the backfill page checkpoint."""
        await self._upsert_checkpoint(
            entity_type=BACKFILL_CHECKPOINT_TYPE,
            last_record_id=str(page),
            increment=0,
        )

    # ── Query helpers ─────────────────────────────────────────────────────

    async def _get_existing_tone(self, tone_id: int) -> T3KToneStaging | None:
        stmt = select(T3KToneStaging).where(T3KToneStaging.id == tone_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _count_staged_models(self, tone_id: int) -> int:
        stmt = select(func.count()).where(T3KModelStaging.tone_id == tone_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def _get_staged_models(self, tone_id: int) -> list[T3KModelStaging]:
        stmt = select(T3KModelStaging).where(T3KModelStaging.tone_id == tone_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _read_backfill_page(self) -> int:
        stmt = select(SyncCheckpoint).where(
            SyncCheckpoint.source_name == "t3k",
            SyncCheckpoint.entity_type == BACKFILL_CHECKPOINT_TYPE,
        )
        result = await self._session.execute(stmt)
        cp = result.scalar_one_or_none()
        return int(cp.last_record_id) if cp else 1

    # ── API wrappers (with tracking) ─────────────────────────────────────

    async def _api_get_tones(self, page: int = 1, sort: str = "newest") -> list:
        try:
            result = await self._api.get_tones(page=page, page_size=TONES_PAGE_SIZE, sort=sort)
            self._tracker.record_success()
            return result
        except Exception:
            self._tracker.record_failure()
            raise

    async def _api_get_models(self, tone_id: int) -> list:
        try:
            result = await self._api.get_models(tone_id)
            self._tracker.record_success()
            return result
        except Exception:
            self._tracker.record_failure()
            raise

    # ── Result builder ────────────────────────────────────────────────────

    def _build_result(
        self,
        mode: SyncMode,
        page: int,
        tone_results: list[TonePackageResult],
        *,
        hit_known: bool = False,
        reached_end: bool = False,
    ) -> SyncBatchResult:
        return SyncBatchResult(
            mode=mode,
            page=page,
            tones_processed=sum(1 for r in tone_results if not r.skipped and r.error is None),
            tones_skipped=sum(1 for r in tone_results if r.skipped),
            models_staged=sum(r.models_staged for r in tone_results),
            files_downloaded=sum(r.files_downloaded for r in tone_results),
            api_calls_made=sum(r.api_calls for r in tone_results),
            api_calls_failed=sum(1 for r in tone_results if r.error is not None),
            hit_known_tone=hit_known,
            reached_end=reached_end,
            tone_results=tone_results,
        )
