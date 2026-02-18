"""SOURCE_SYNC Job Handler — batch-then-exit model.

Acquires a non-destructive Redis lock, runs one sync batch via
T3KSyncService.run_sync_batch(), logs the result, releases lock, exits.
Scheduler re-triggers after 60s if lock is gone.
"""

import logging
import os
from pathlib import Path
from uuid import UUID

import redis.asyncio as redis

from core.domain.auth_gate import check_auth_status
from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import SyncMode
from source_t3k.services.model_downloader import ModelDownloader
from source_t3k.services.sync_service import T3KSyncService
from worker.config import WorkerSettings
from worker.db import get_t3k_session_no_tx
from worker.main import broker

logger = logging.getLogger(__name__)

SYNC_SOURCE = "t3k"
SYNC_LOCK_TTL_SECONDS = 600  # 10 minutes; renewed during sync


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


def _build_model_downloader(api_client: T3KAPIClient) -> ModelDownloader:
    """Build model downloader rooted under the processed volume.

    Shares the API client's httpx client so downloads use the same
    browser-like headers and cookies, avoiding Vercel bot detection.
    """
    base_path = Path(os.environ["GTS_STORAGE_ROOT"]) / "source_downloads" / "t3k"
    return ModelDownloader(
        base_path=base_path,
        http_client=api_client._client,
        get_auth_headers=api_client._get_auth_headers,
        rate_limiter=api_client._rate_limiter,
    )


def _get_sync_mode() -> SyncMode:
    """Read sync mode from T3K_SYNC_MODE env var."""
    raw = os.getenv("T3K_SYNC_MODE", "bau").lower()
    if raw == "catch_up":
        return SyncMode.CATCH_UP
    return SyncMode.BAU


@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    """Handle SOURCE_SYNC job: one batch, then exit."""
    _check_auth_gate()
    settings = WorkerSettings()  # type: ignore[call-arg]
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    lock_key = f"{SYNC_SOURCE}:sync:lock"
    lock_value = str(job_id)

    # Non-destructive lock: if held, exit cleanly
    acquired = await redis_client.set(lock_key, lock_value, nx=True, ex=SYNC_LOCK_TTL_SECONDS)
    if not acquired:
        logger.info("Sync lock held by another job, exiting")
        await redis_client.aclose()
        return

    token_manager = None
    try:
        async with get_t3k_session_no_tx() as session:
            token_manager, api_client = _build_api_client()
            model_downloader = _build_model_downloader(api_client)
            publisher = GearSyncPublisher(session=session, queue_name="gear_sync")
            sync_service = T3KSyncService(
                api_client=api_client,
                session=session,
                model_downloader=model_downloader,
            )

            async def renew_lock() -> None:
                await redis_client.expire(lock_key, SYNC_LOCK_TTL_SECONDS)

            mode = _get_sync_mode()
            result = await sync_service.run_sync_batch(publisher, mode=mode, on_progress=renew_lock)

            logger.info(
                "Sync batch complete: mode=%s tones=%d skipped=%d models=%d "
                "files=%d api_calls=%d hit_known=%s",
                result.mode.value,
                result.tones_processed,
                result.tones_skipped,
                result.models_staged,
                result.files_downloaded,
                result.api_calls_made,
                result.hit_known_tone,
            )
    finally:
        if token_manager is not None:
            await token_manager.close()
        # Only release if we're still the lock holder
        current = await redis_client.get(lock_key)
        if current == lock_value:
            await redis_client.delete(lock_key)
        await redis_client.aclose()


# Add task_id attribute for TaskIQ compatibility
handle_source_sync.task_id = handle_source_sync.task_name  # type: ignore[attr-defined]
