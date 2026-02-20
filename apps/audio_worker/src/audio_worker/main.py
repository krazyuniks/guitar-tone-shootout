"""FastAPI app entrypoint for the audio-worker container."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from audio_worker.consumer import ProcessAudioConsumer
from worker.db import get_core_session_no_tx


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the process_audio consumer for container lifetime."""
    async with get_core_session_no_tx() as session:
        consumer = ProcessAudioConsumer(session)

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


app = FastAPI(title="GTS Audio Worker", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Container health endpoint."""
    return {"status": "healthy"}
