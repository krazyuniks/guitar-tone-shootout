"""WebSocket endpoints for real-time updates."""

import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.core.redis import subscribe_job_progress
from app.core.security import TokenError, decode_access_token
from app.models.job import Job
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter()


async def verify_ws_token(token: str) -> User | None:
    """Verify WebSocket authentication token.

    Args:
        token: JWT token from query parameter.

    Returns:
        User if valid, None otherwise.
    """
    try:
        user_id = decode_access_token(token)
    except TokenError:
        return None

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        return result.scalar_one_or_none()


async def get_job_for_user(user_id: UUID, job_id: str) -> Job | None:
    """Get job if it belongs to the user.

    Args:
        user_id: The user's UUID.
        job_id: The job ID as string.

    Returns:
        Job if found and owned by user, None otherwise.
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return None

    async with async_session_factory() as db:
        result = await db.execute(
            select(Job).where(Job.id == job_uuid, Job.user_id == user_id)
        )
        return result.scalar_one_or_none()


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(
    websocket: WebSocket,
    job_id: str,
    token: str | None = None,
) -> None:
    """WebSocket endpoint for real-time job progress updates.

    Clients connect with a token query parameter for authentication.
    Progress updates are pushed via Redis pub/sub from workers.

    Args:
        websocket: The WebSocket connection.
        job_id: The job UUID to subscribe to.
        token: JWT authentication token (query param).
    """
    # Validate token
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Validate job ownership
    job = await get_job_for_user(user.id, job_id)
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    await websocket.accept()
    logger.info("WebSocket connected for job %s by user %s", job_id, user.username)

    # Subscribe to Redis channel for this job
    pubsub = await subscribe_job_progress(job_id)

    try:
        # Send initial job status
        await websocket.send_json(
            {
                "type": "status",
                "job_id": str(job.id),
                "status": job.status.value,
                "progress": job.progress,
                "message": job.message,
            }
        )

        # Listen for Redis pub/sub messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

                # Close connection when job completes
                if data.get("status") in ("completed", "failed", "cancelled"):
                    status = data["status"]
                    logger.info("Job %s finished with status %s", job_id, status)
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    except Exception as e:
        logger.error("WebSocket error for job %s: %s", job_id, e)
    finally:
        await pubsub.unsubscribe(f"job:{job_id}:progress")
        await pubsub.close()
