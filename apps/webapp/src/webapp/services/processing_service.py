"""Processing service for triggering background jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException

if TYPE_CHECKING:
    from uuid import UUID


async def enqueue_to_worker(job_id: UUID) -> None:
    """Enqueue a job to the worker admin API.

    Sends an HTTP POST to the worker admin API with the job ID
    for background task execution.

    Args:
        job_id: The job ID to enqueue

    Raises:
        HTTPException: 502 if the worker is unreachable or returns an error
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://worker:8001/api/admin/enqueue",
                json={"job_id": str(job_id)},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Worker returned an error") from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail="Worker is unreachable") from e
