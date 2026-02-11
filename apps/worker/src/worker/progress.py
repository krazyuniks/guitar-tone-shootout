"""Progress publisher for job progress updates via Redis pub/sub.

Publishes job progress to Redis channels for WebSocket forwarding to clients.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from uuid import UUID


async def publish_progress(
    redis_url: str,
    job_id: UUID,
    progress: int,
    status: str,
    message: str,
) -> None:
    """Publish job progress update to Redis pub/sub channel.

    Args:
        redis_url: Redis connection URL
        job_id: Job identifier
        progress: Progress percentage (clamped to 0-100)
        status: Job status (running, completed, failed)
        message: Progress message

    Publishes to channel: job_progress:{job_id}
    Message format:
        {
            "job_id": "uuid-string",
            "progress": 0-100,
            "status": "running",
            "message": "Processing...",
            "terminal": true  # only for completed/failed
        }

    Handles Redis errors gracefully (does not raise exceptions).
    Always closes Redis connection after publish.
    """
    client = None
    try:
        # Create Redis client
        client = aioredis.from_url(redis_url)

        # Clamp progress to 0-100 range
        clamped_progress = min(100, max(0, progress))

        # Build message payload
        payload = {
            "job_id": str(job_id),
            "progress": clamped_progress,
            "status": status,
            "message": message,
        }

        # Add terminal flag for completed/failed statuses
        if status in ("completed", "failed"):
            payload["terminal"] = True

        # Publish to job-specific channel
        channel = f"job_progress:{job_id}"
        await client.publish(channel, json.dumps(payload))

    except Exception:
        # Handle all errors gracefully (connection, publish, etc.)
        pass

    finally:
        # Always close Redis connection
        if client is not None:
            await client.close()
            await client.wait_closed()
