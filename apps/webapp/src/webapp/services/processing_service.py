"""Processing service for triggering background jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from uuid import UUID


async def enqueue_to_worker(job_id: UUID) -> None:
    """Enqueue a job to the worker admin API.

    Sends an HTTP POST to the worker admin API with the job ID
    for background task execution.

    Args:
        job_id: The job ID to enqueue
    """
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://worker:8001/api/admin/enqueue",
            json={"job_id": str(job_id)},
        )
