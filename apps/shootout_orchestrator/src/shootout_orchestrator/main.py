"""FastAPI app entrypoint for the shootout-orchestrator container."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from messaging.db import get_core_session_no_tx
from shootout_orchestrator.consumer import StartShootoutConsumer


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the start_shootout consumer for container lifetime."""
    async with get_core_session_no_tx() as session:
        consumer = StartShootoutConsumer(session)

        await consumer.message_bus.create_queue(consumer.queue_name)
        await consumer.message_bus.create_queue(consumer.dead_letter_queue)
        await session.commit()

        consumer_task = asyncio.create_task(consumer.run())

        try:
            yield
        finally:
            consumer.request_shutdown()
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


app = FastAPI(title="GTS Shootout Orchestrator", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Container health endpoint."""
    return {"status": "healthy"}
