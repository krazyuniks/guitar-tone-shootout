"""Webapp Admin API - FastAPI router for admin management.

No authentication required. Access is controlled at the network level
(port not exposed publicly). Provides health checks and job management.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand, StartShootoutCommand
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.api.v1.schemas.admin import (
    EnqueueRequest,
    EnqueueResponse,
    ErrorsSummaryResponse,
    JobDetail,
    JobSummary,
    PendingRetriesCountResponse,
    SyncTriggerResponse,
    UnlockResponse,
)
from webapp.dependencies import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Track app start time for uptime calculation
_app_start_time = time.monotonic()


async def _get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency alias for clarity in this module."""
    async for session in get_db():
        yield session


async def check_database_connectivity(session: AsyncSession) -> str:
    """Check database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"


# Known source names
KNOWN_SOURCES = {"t3k"}


def validate_source(source: str) -> None:
    """Validate source name, raise 404 if unknown."""
    if source not in KNOWN_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")


@router.get("/health")
async def health_check(session: AsyncSession = Depends(_get_db)) -> dict[str, str | float]:
    """Health check — database connectivity and uptime."""
    database_status = await check_database_connectivity(session)
    uptime = time.monotonic() - _app_start_time
    overall_status = "healthy" if database_status == "connected" else "unhealthy"
    return {
        "status": overall_status,
        "database": database_status,
        "uptime": uptime,
    }


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    session: AsyncSession = Depends(_get_db),
) -> list[JobSummary]:
    """List jobs with optional status and job_type filters."""
    stmt = select(Job)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    if job_type is not None:
        stmt = stmt.where(Job.job_type == job_type)
    stmt = stmt.order_by(Job.created_at.desc())
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return [JobSummary.model_validate(job) for job in jobs]


@router.get("/jobs/dead-lettered", response_model=list[JobSummary])
async def list_dead_lettered_jobs(
    session: AsyncSession = Depends(_get_db),
) -> list[JobSummary]:
    """List all dead-lettered jobs."""
    stmt = select(Job).where(Job.status == JobStatus.DEAD_LETTERED).order_by(Job.created_at.desc())
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return [JobSummary.model_validate(job) for job in jobs]


@router.get("/jobs/pending-retries/count", response_model=PendingRetriesCountResponse)
async def get_pending_retries_count(
    session: AsyncSession = Depends(_get_db),
) -> PendingRetriesCountResponse:
    """Count jobs with pending retries."""
    stmt = select(Job).where(Job.next_retry_at.is_not(None))
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return PendingRetriesCountResponse(count=len(jobs))


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(_get_db),
) -> JobDetail:
    """Get detailed job information including child jobs."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    children_result = await session.execute(select(Job).where(Job.parent_job_id == job_id))
    children = children_result.scalars().all()

    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]
    return job_detail


@router.post("/jobs/{job_id}/cancel", response_model=JobDetail)
async def cancel_job(
    job_id: UUID,
    session: AsyncSession = Depends(_get_db),
) -> JobDetail:
    """Cancel a job by setting its status to CANCELLED."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    terminal_states = {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.DEAD_LETTERED,
    }
    if job.status in terminal_states:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in {job.status.value} state",
        )

    job.status = JobStatus.CANCELLED
    await session.flush()
    await session.refresh(job)

    children_result = await session.execute(select(Job).where(Job.parent_job_id == job_id))
    children = children_result.scalars().all()

    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]
    return job_detail


@router.post("/jobs/{job_id}/retry", response_model=JobDetail)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(_get_db),
) -> JobDetail:
    """Retry a failed or dead-lettered job by resetting it to PENDING."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    retryable_states = {JobStatus.FAILED, JobStatus.DEAD_LETTERED}
    if job.status not in retryable_states:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry job in {job.status.value} state",
        )

    job.status = JobStatus.PENDING
    job.error = None
    await session.flush()
    await session.refresh(job)

    children_result = await session.execute(select(Job).where(Job.parent_job_id == job_id))
    children = children_result.scalars().all()

    job_detail = JobDetail.model_validate(job)
    job_detail.children = [JobSummary.model_validate(child) for child in children]
    return job_detail


@router.post("/enqueue", response_model=EnqueueResponse, status_code=202)
async def enqueue_job(
    request: EnqueueRequest,
    session: AsyncSession = Depends(_get_db),
) -> EnqueueResponse:
    """Enqueue a job to the appropriate pgmq queue."""
    result = await session.execute(select(Job).where(Job.id == request.job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    pgmq = PgmqClient(session)

    if job.job_type == JobType.SOURCE_SYNC:
        raise HTTPException(
            status_code=400,
            detail="SOURCE_SYNC is self-managed by t3k-sync",
        )
    elif job.job_type == JobType.SHOOTOUT:
        cmd = StartShootoutCommand(source_bc="webapp", payload={"job_id": str(job.id)})
        await pgmq.send("shootout_commands", cmd)
    elif (
        job.job_type in (JobType.SHOOTOUT_AUDIO, JobType.SHOOTOUT_MASTER)
        or job.job_type == JobType.AUDIO_PROCESSING
    ):
        cmd_audio = ProcessAudioCommand(
            source_bc="webapp",
            payload={
                "job_id": str(job.id),
                "shootout_id": str(job.entity_id),
                "user_id": str(job.user_id),
            },
        )
        await pgmq.send("audio_commands", cmd_audio)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"No handler registered for job type: {job.job_type.value}",
        )

    await session.flush()
    return EnqueueResponse(id=request.job_id)


@router.post("/sources/{source}/sync", response_model=SyncTriggerResponse, status_code=202)
async def trigger_sync(
    source: str,
    session: AsyncSession = Depends(_get_db),
) -> SyncTriggerResponse:
    """Trigger a manual sync for a source (creates a pending SOURCE_SYNC job)."""
    validate_source(source)

    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SOURCE_SYNC,
        status=JobStatus.PENDING,
        progress=0,
        attempt=1,
        max_attempts=3,
    )
    session.add(job)
    await session.flush()

    return SyncTriggerResponse(message=f"Sync triggered for {source}")


@router.get("/sources/{source}/errors/summary", response_model=ErrorsSummaryResponse)
async def get_errors_summary(
    source: str,
    session: AsyncSession = Depends(_get_db),
) -> ErrorsSummaryResponse:
    """Get error summary for a source."""
    validate_source(source)

    cutoff_time = datetime.now(UTC) - timedelta(hours=24)
    stmt = select(Job).where(
        Job.status == JobStatus.FAILED,
        Job.completed_at >= cutoff_time,
    )
    result = await session.execute(stmt)
    failed_jobs = result.scalars().all()

    errors: dict[str, int] = {}
    for job in failed_jobs:
        if job.error:
            errors[job.error] = errors.get(job.error, 0) + 1

    return ErrorsSummaryResponse(errors=errors, time_window_hours=24)


@router.post("/sources/{source}/sync/unlock", response_model=UnlockResponse)
async def unlock_sync(source: str) -> UnlockResponse:
    """No-op: PG advisory lock is released automatically when sync completes."""
    validate_source(source)
    return UnlockResponse(message=f"Sync lock for {source} is managed by PostgreSQL advisory lock")


@router.post("/scheduler/unlock", response_model=UnlockResponse)
async def unlock_scheduler() -> UnlockResponse:
    """No-op: PG advisory lock is released automatically when scheduler completes."""
    return UnlockResponse(message="Scheduler lock is managed by PostgreSQL advisory lock")
