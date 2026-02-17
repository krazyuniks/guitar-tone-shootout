"""WebSocket endpoints for real-time job progress updates."""

from __future__ import annotations

import contextlib
import json
import os
from uuid import UUID

import jwt
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.auth.token import decode_access_token
from webapp.dependencies import get_db

router = APIRouter(prefix="/ws", tags=["websocket"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "dead_lettered"}


@router.websocket("/jobs/{job_id}")
async def job_progress_ws(
    websocket: WebSocket,
    job_id: UUID,
) -> None:
    """Stream real-time job progress via WebSocket.

    Authentication: JWT token via ?token= query parameter (cookies not
    available in WebSocket handshake in all browsers).

    Subscribes to Redis pub/sub channel job_progress:{job_id} and forwards
    messages to the client. Auto-closes on terminal job state.

    Args:
        websocket: The WebSocket connection
        job_id: The job ID to monitor
    """
    await websocket.accept()

    # Authenticate via ?token= query param (JWT cookie not available in WS)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_text(json.dumps({"error": "Missing token"}))
        await websocket.close(code=4001)
        return

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        await websocket.send_text(json.dumps({"error": "Invalid token"}))
        await websocket.close(code=4001)
        return

    # Validate job ownership using a fresh DB session
    async for db in get_db():
        stmt = select(JobModel).where(JobModel.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job or job.user_id != user_id:
            await websocket.send_text(json.dumps({"error": "Job not found"}))
            await websocket.close(code=4004)
            return

        # Send current state immediately
        await websocket.send_text(
            json.dumps(
                {
                    "job_id": str(job.id),
                    "progress": job.progress,
                    "status": job.status.value,
                    "message": job.message or "",
                }
            )
        )

        # If job already terminal, close immediately
        if job.status.value in TERMINAL_STATUSES:
            await websocket.close()
            return
        break

    # Subscribe to Redis pub/sub and forward messages
    redis_client = None
    pubsub = None
    try:
        redis_client = aioredis.from_url(REDIS_URL)
        pubsub = redis_client.pubsub()
        channel = f"job_progress:{job_id}"
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            await websocket.send_text(json.dumps(data))

            # Close on terminal state
            if data.get("terminal") or data.get("status") in TERMINAL_STATUSES:
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe()
            await pubsub.close()
        if redis_client is not None:
            await redis_client.close()
        with contextlib.suppress(Exception):
            await websocket.close()
