"""Progress publisher for job progress updates via PostgreSQL LISTEN/NOTIFY."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


async def publish_progress(
    session: AsyncSession,
    job_id: UUID,
    progress: int,
    status: str,
    message: str,
) -> None:
    """Publish job progress update via pg_notify.

    Args:
        session: Active database session
        job_id: Job identifier
        progress: Progress percentage (clamped to 0-100)
        status: Job status (running, completed, failed)
        message: Progress message
    """
    payload: dict[str, object] = {
        "job_id": str(job_id),
        "progress": min(100, max(0, progress)),
        "status": status,
        "message": message,
    }
    if status in ("completed", "failed"):
        payload["terminal"] = True

    await session.execute(
        text("SELECT pg_notify('job_progress', :payload)"),
        {"payload": json.dumps(payload)},
    )
