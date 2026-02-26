"""WebSocket endpoints for real-time job progress updates."""

from __future__ import annotations

import asyncio
import contextlib
import json
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.auth.token import decode_access_token
from webapp.dependencies import _session_factory, get_db

router = APIRouter(prefix="/ws", tags=["websocket"])

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "dead_lettered"}


@router.websocket("/jobs/{job_id}")
async def job_progress_ws(
    websocket: WebSocket,
    job_id: UUID,
) -> None:
    """Stream real-time job progress via WebSocket.

    Authentication: JWT token via ?token= query parameter (cookies not
    available in WebSocket handshake in all browsers).

    Subscribes to PostgreSQL LISTEN job_progress channel and forwards
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

    # Subscribe to PostgreSQL LISTEN and forward progress notifications
    if _session_factory is None:
        with contextlib.suppress(Exception):
            await websocket.close()
        return

    engine = _session_factory.kw.get("bind")
    if engine is None:
        with contextlib.suppress(Exception):
            await websocket.close()
        return

    try:
        async with engine.connect() as conn:
            raw_conn = await conn.get_raw_connection()
            asyncpg_conn = raw_conn.driver_connection

            queue: asyncio.Queue[dict] = asyncio.Queue()

            def on_notify(_conn, _pid, _channel, pg_payload):
                data = json.loads(pg_payload)
                if str(data.get("job_id")) == str(job_id):
                    queue.put_nowait(data)

            await asyncpg_conn.add_listener("job_progress", on_notify)
            try:
                while True:
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except TimeoutError:
                        continue
                    await websocket.send_text(json.dumps(data))
                    if data.get("terminal") or data.get("status") in TERMINAL_STATUSES:
                        break
            except WebSocketDisconnect:
                pass
            finally:
                await asyncpg_conn.remove_listener("job_progress", on_notify)
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
