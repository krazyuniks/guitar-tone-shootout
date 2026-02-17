"""SOURCE_SYNC Job Handler.

This module provides the SOURCE_SYNC job handler that orchestrates
T3K catalog synchronisation by creating sync services and running
the catalog sync process.
"""

import asyncio
import contextlib
import os
from pathlib import Path
from uuid import UUID

import redis.asyncio as redis

from core.domain.auth_gate import check_auth_status
from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.services.model_downloader import ModelDownloader
from source_t3k.services.sync_service import T3KSyncService
from worker.config import WorkerSettings
from worker.db import get_t3k_session_no_tx
from worker.main import broker

SYNC_SOURCE = "t3k"
SYNC_LOCK_TTL_SECONDS = 120
SYNC_LOCK_RENEW_SECONDS = 30


def _check_auth_gate(auth_file_path: str | None = None) -> None:
    """Check auth status before making any T3K API calls."""
    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    status = check_auth_status(auth_file_path)
    if not status.can_proceed():
        msg = f"T3K auth status is {status.value}"
        if status.needs_login():
            msg += " — run `just t3k-login`"
        raise RuntimeError(msg)


def _build_api_client() -> tuple[T3KTokenManager, T3KAPIClient]:
    """Build T3K token manager + API client from environment configuration."""
    base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")
    auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    encryption_key = os.environ["OAUTH_ENCRYPTION_KEY"]
    token_manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    api_client = T3KAPIClient(
        token_manager=token_manager, base_url=base_url, requests_per_second=1.0
    )
    return token_manager, api_client


def _build_model_downloader(session, api_client: T3KAPIClient) -> ModelDownloader:
    """Build model downloader rooted under the processed volume.

    Shares the API client's httpx client so downloads use the same
    browser-like headers and cookies, avoiding Vercel bot detection.
    """
    base_path = Path(os.environ["GTS_STORAGE_ROOT"]) / "source_downloads" / "t3k"
    return ModelDownloader(
        base_path=base_path,
        session=session,
        http_client=api_client._client,
        get_auth_headers=api_client._get_auth_headers,
        rate_limiter=api_client._rate_limiter,
    )


async def _renew_sync_lock(redis_client: redis.Redis, lock_key: str) -> None:
    """Continuously renew sync lock TTL while the sync job is running."""
    while True:
        await asyncio.sleep(SYNC_LOCK_RENEW_SECONDS)
        await redis_client.expire(lock_key, SYNC_LOCK_TTL_SECONDS)


@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    """Handle SOURCE_SYNC job by creating T3K sync service and running catalog sync."""
    _check_auth_gate()  # Fail fast — no API calls if auth unhealthy
    settings = WorkerSettings()  # type: ignore[call-arg]
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    lock_key = f"{SYNC_SOURCE}:sync:lock"
    lock_value = str(job_id)

    acquired = await redis_client.set(
        lock_key,
        lock_value,
        nx=True,
        ex=SYNC_LOCK_TTL_SECONDS,
    )
    if not acquired:
        # Stale lock from a killed process — force-delete and re-acquire.
        await redis_client.delete(lock_key)
        acquired = await redis_client.set(
            lock_key,
            lock_value,
            nx=True,
            ex=SYNC_LOCK_TTL_SECONDS,
        )
        if not acquired:
            await redis_client.aclose()
            return

    renew_task = asyncio.create_task(_renew_sync_lock(redis_client, lock_key))
    token_manager = None
    try:
        async with get_t3k_session_no_tx() as session:
            token_manager, api_client = _build_api_client()
            model_downloader = _build_model_downloader(session, api_client)
            publisher = GearSyncPublisher(session=session, queue_name="gear_sync")
            sync_service = T3KSyncService(
                api_client=api_client,
                session=session,
                model_downloader=model_downloader,
            )
            await sync_service.run_catalog_sync(publisher)
    finally:
        renew_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await renew_task

        if token_manager is not None:
            await token_manager.close()

        # Only release if we're still the lock holder.
        current_lock_value = await redis_client.get(lock_key)
        if current_lock_value == lock_value:
            await redis_client.delete(lock_key)
        await redis_client.aclose()


@broker.task
async def handle_backfill_downloads(job_id: UUID) -> None:
    """Backfill missing models and NAM files for staged tones, then publish complete tones.

    Phase 1 (no API calls): publish tones that already have all models staged
    and all files on disk.

    Phase 2 (API calls): for tones needing downloads, fetch models and files.
    Stops immediately on first API error (Vercel challenge, rate limit, auth)
    to avoid hammering the upstream.
    """
    import logging
    from pathlib import PurePosixPath

    from sqlalchemy import func, select

    from source_t3k.adapters.inbound.exceptions import T3KAPIError
    from source_t3k.adapters.outbound.models import T3KModelStaging, T3KToneStaging

    logger = logging.getLogger(__name__)

    _check_auth_gate()
    settings = WorkerSettings()  # type: ignore[call-arg]
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    lock_key = f"{SYNC_SOURCE}:backfill:lock"
    lock_value = str(job_id)

    acquired = await redis_client.set(lock_key, lock_value, nx=True, ex=SYNC_LOCK_TTL_SECONDS)
    if not acquired:
        await redis_client.delete(lock_key)
        acquired = await redis_client.set(lock_key, lock_value, nx=True, ex=SYNC_LOCK_TTL_SECONDS)
        if not acquired:
            await redis_client.aclose()
            return

    renew_task = asyncio.create_task(_renew_sync_lock(redis_client, lock_key))
    token_manager = None
    try:
        async with get_t3k_session_no_tx() as session:
            token_manager, api_client = _build_api_client()
            downloader = _build_model_downloader(session, api_client)
            publisher = GearSyncPublisher(session=session, queue_name="gear_sync")
            base_path = downloader._base_path

            # Get all tones with their staged model counts in one query.
            stmt = (
                select(
                    T3KToneStaging,
                    func.count(T3KModelStaging.id).label("staged_count"),
                )
                .outerjoin(T3KModelStaging, T3KModelStaging.tone_id == T3KToneStaging.id)
                .group_by(T3KToneStaging.id)
                .order_by(T3KToneStaging.id)
            )
            result = await session.execute(stmt)
            rows = result.all()
            logger.warning("Backfill: %d tones to check", len(rows))

            tones_published = 0
            tones_need_download = []

            # Phase 1: publish tones that are already complete (no API calls).
            for tone, staged_count in rows:
                if staged_count < tone.models_count:
                    tones_need_download.append((tone, staged_count))
                    continue

                models_result = await session.execute(
                    select(T3KModelStaging).where(T3KModelStaging.tone_id == tone.id)
                )
                models = list(models_result.scalars().all())
                if not models:
                    continue

                all_files_present = True
                for model in models:
                    filename = PurePosixPath(model.model_url).name or f"{model.id}.nam"
                    file_path = base_path / str(model.id) / filename
                    if not file_path.exists():
                        all_files_present = False
                        break

                if all_files_present and len(models) >= tone.models_count:
                    await publisher.publish_tone(tone, models=models)
                    await session.commit()
                    tones_published += 1
                else:
                    tones_need_download.append((tone, staged_count))

            logger.warning(
                "Backfill phase 1: %d tones published (already complete), "
                "%d tones need downloads",
                tones_published,
                len(tones_need_download),
            )

            # Phase 2: fetch missing models/files. Stop on first API error.
            models_fetched = 0
            files_downloaded = 0

            for tone, staged_count in tones_need_download:
                try:
                    if staged_count < tone.models_count:
                        api_models = await api_client.get_models(tone.id)
                        for api_model in api_models:
                            existing = await session.execute(
                                select(T3KModelStaging.id).where(T3KModelStaging.id == api_model.id)
                            )
                            if existing.scalar_one_or_none() is None:
                                staging_model = T3KModelStaging.from_domain(api_model)
                                session.add(staging_model)
                                models_fetched += 1
                        await session.flush()
                except T3KAPIError as exc:
                    logger.error(
                        "Backfill stopping: API error fetching models for tone %s: %s",
                        tone.id,
                        exc,
                    )
                    break

                models_result = await session.execute(
                    select(T3KModelStaging).where(T3KModelStaging.tone_id == tone.id)
                )
                models = list(models_result.scalars().all())
                if not models:
                    continue

                all_files_present = True
                for model in models:
                    filename = PurePosixPath(model.model_url).name or f"{model.id}.nam"
                    file_path = base_path / str(model.id) / filename
                    if file_path.exists():
                        continue
                    try:
                        downloaded = await downloader.download_model(model)
                    except T3KAPIError as exc:
                        logger.error(
                            "Backfill stopping: API error downloading model %s: %s",
                            model.id,
                            exc,
                        )
                        all_files_present = False
                        break
                    if downloaded is not None:
                        files_downloaded += 1
                    else:
                        all_files_present = False
                else:
                    # Only publish if the inner loop completed without break.
                    if all_files_present and len(models) >= tone.models_count:
                        await publisher.publish_tone(tone, models=models)
                        await session.commit()
                        tones_published += 1
                    continue
                # Inner loop broke — stop processing further tones.
                break

            logger.warning(
                "Backfill complete: %d tones published, %d models fetched, " "%d files downloaded",
                tones_published,
                models_fetched,
                files_downloaded,
            )
    finally:
        renew_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await renew_task
        if token_manager is not None:
            await token_manager.close()
        current_lock_value = await redis_client.get(lock_key)
        if current_lock_value == lock_value:
            await redis_client.delete(lock_key)
        await redis_client.aclose()


# Add task_id attributes for TaskIQ compatibility
handle_source_sync.task_id = handle_source_sync.task_name  # type: ignore[attr-defined]
handle_backfill_downloads.task_id = handle_backfill_downloads.task_name  # type: ignore[attr-defined]
