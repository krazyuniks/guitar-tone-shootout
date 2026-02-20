"""FastAPI app entrypoint for the t3k-sync container."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from t3k_sync.consumer import GearSyncConsumer
from t3k_sync.scheduler import SyncScheduler
from worker.db import get_core_session_no_tx


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start consumer and scheduler background tasks for container lifetime."""
    async with get_core_session_no_tx() as session:
        consumer = GearSyncConsumer(session)
        scheduler = SyncScheduler(interval_seconds=60.0)

        await consumer.message_bus.create_queue(consumer.queue_name)
        await consumer.message_bus.create_queue(consumer.dead_letter_queue)
        await session.commit()

        consumer_task = asyncio.create_task(consumer.run())
        scheduler_task = asyncio.create_task(scheduler.run())

        try:
            yield
        finally:
            consumer.request_shutdown()
            scheduler.request_shutdown()

            consumer_task.cancel()
            scheduler_task.cancel()
            await asyncio.gather(consumer_task, scheduler_task, return_exceptions=True)


app = FastAPI(title="GTS T3K Sync", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Container health endpoint."""
    return {"status": "healthy"}
