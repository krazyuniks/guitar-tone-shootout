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
    api_client = T3KAPIClient(token_manager=token_manager, base_url=base_url)
    return token_manager, api_client


def _build_model_downloader(session) -> ModelDownloader:
    """Build model downloader rooted under the processed volume."""
    base_path = Path(os.getenv("T3K_SOURCE_DOWNLOADS_PATH", "/app/processed/source_downloads/t3k"))
    return ModelDownloader(base_path=base_path, session=session)


async def _renew_sync_lock(redis_client: redis.Redis, lock_key: str) -> None:
    """Continuously renew sync lock TTL while the sync job is running."""
    while True:
        await asyncio.sleep(SYNC_LOCK_RENEW_SECONDS)
        await redis_client.expire(lock_key, SYNC_LOCK_TTL_SECONDS)


@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    """Handle SOURCE_SYNC job by creating T3K sync service and running catalog sync."""
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
        await redis_client.aclose()
        return

    renew_task = asyncio.create_task(_renew_sync_lock(redis_client, lock_key))
    token_manager = None
    try:
        async with get_t3k_session_no_tx() as session:
            token_manager, api_client = _build_api_client()
            model_downloader = _build_model_downloader(session)
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


# Add task_id attribute for TaskIQ compatibility
handle_source_sync.task_id = handle_source_sync.task_name  # type: ignore[attr-defined]
