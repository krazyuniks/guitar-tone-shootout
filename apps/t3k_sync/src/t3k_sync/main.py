"""FastAPI app entrypoint for the t3k-sync container."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

from fastapi import FastAPI

from messaging.db import get_core_session_no_tx
from t3k_sync.consumer import GearSyncConsumer
from t3k_sync.health import SyncHealthTracker
from t3k_sync.scheduler import SyncScheduler
from t3k_sync.source_sync import build_token_manager
from t3k_sync.tasks import (
    backup_all_databases,
    dispatch_pending_jobs,
    monitor_stale_jobs,
    process_pending_retries,
    refresh_t3k_token,
)

logger = logging.getLogger(__name__)

# Module-level tracker so the health endpoint can read it.
_tracker = SyncHealthTracker()


async def _run_periodic(
    name: str,
    coro_fn: Callable[[], Coroutine[Any, Any, None]],
    interval: float,
    shutdown: asyncio.Event,
) -> None:
    """Run coro_fn on a fixed interval until shutdown is signalled."""
    while not shutdown.is_set():
        try:
            await coro_fn()
        except Exception:
            logger.exception("Scheduled task %s failed", name)
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start consumer, sync scheduler, and periodic tasks for container lifetime."""
    token_manager = build_token_manager()

    async with get_core_session_no_tx() as session:
        consumer = GearSyncConsumer(session)
        scheduler = SyncScheduler(
            interval_seconds=60.0, tracker=_tracker, token_manager=token_manager
        )

        await consumer.message_bus.create_queue(consumer.queue_name)
        await consumer.message_bus.create_queue(consumer.dead_letter_queue)
        await session.commit()

        periodic_tasks: list[tuple[str, Callable[[], Coroutine[Any, Any, None]], float]] = [
            ("refresh_t3k_token", partial(refresh_t3k_token, token_manager=token_manager), 300.0),
            ("monitor_stale_jobs", monitor_stale_jobs, 120.0),
            ("process_pending_retries", process_pending_retries, 120.0),
            ("dispatch_pending_jobs", dispatch_pending_jobs, 120.0),
            ("backup_all_databases", backup_all_databases, 43200.0),
        ]

        shutdown = asyncio.Event()
        consumer_task = asyncio.create_task(consumer.run())
        scheduler_task = asyncio.create_task(scheduler.run())
        periodic = [
            asyncio.create_task(_run_periodic(name, fn, interval, shutdown))
            for name, fn, interval in periodic_tasks
        ]

        try:
            yield
        finally:
            consumer.request_shutdown()
            scheduler.request_shutdown()
            shutdown.set()

            all_tasks = [consumer_task, scheduler_task, *periodic]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)

            await token_manager.close()


app = FastAPI(title="GTS T3K Sync", version="0.1.0", lifespan=lifespan)

# Admin API endpoints for T3K sync management
from t3k_sync.api.admin import router as admin_router  # noqa: E402

app.include_router(admin_router)


@app.get("/health")
async def health() -> dict[str, str | None]:
    """Container health endpoint.

    Returns 200 for healthy and degraded (don't trigger Docker restart).
    Degraded includes reason and timestamp for observability.
    """
    return _tracker.health_response()
