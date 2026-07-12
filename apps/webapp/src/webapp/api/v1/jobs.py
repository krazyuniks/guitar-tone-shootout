"""Job API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.entities.job import Job as JobEntity
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.api.v1.schemas.job import JobResponse
from webapp.auth.dependencies import CurrentUser, get_db_session
from webapp.services.job_dispatch import enqueue_job
from webapp.services.job_service import JobService
from webapp.services.job_transitions import InvalidTransitionError, transition_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_response(
    job: JobEntity | JobModel, *, children: list[JobResponse] | None = None
) -> JobResponse:
    """Project a domain or persistence job into the authenticated API shape."""
    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        entity_id=job.entity_id,
        parent_job_id=job.parent_job_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        children=children or [],
    )


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    job_type: Annotated[JobType | None, Query(alias="job_type")] = None,
) -> list[JobResponse]:
    """List current user's jobs.

    Protected endpoint - requires authentication.
    Returns only the current user's jobs.

    Args:
        db: Database session
        current_user: Currently authenticated user
        status_filter: Optional status filter (e.g., "running", "completed")
        job_type: Optional job type filter (e.g., "audio_processing")

    Returns:
        List of user's jobs
    """
    service = JobService(db)

    jobs = await service.get_by_user_id(
        current_user.id,
        status=status_filter,
        job_type=job_type,
    )

    return [_job_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
) -> JobResponse:
    """Get a job by ID.

    Protected endpoint - requires authentication.
    Returns 404 if job not found or not owned by user.

    Args:
        job_id: Job ID to retrieve
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Job details

    Raises:
        HTTPException: 404 if job not found or not owned by user
    """
    service = JobService(db)

    tree = await service.get_tree_by_id(job_id, current_user.id)

    if tree is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    job, children = tree
    return _job_response(job, children=[_job_response(child) for child in children])


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
) -> JobResponse:
    """Retry a failed job.

    Protected endpoint - requires authentication.
    Only FAILED jobs owned by the current user can be retried.
    Transitions job to PENDING and re-enqueues it.

    Args:
        job_id: Job ID to retry
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Updated job details

    Raises:
        HTTPException: 404 if job not found or not owned by user
        HTTPException: 409 if job is not in FAILED status
    """
    stmt = select(JobModel).where(JobModel.id == job_id, JobModel.user_id == current_user.id)
    result = await db.execute(stmt)
    job_model = result.scalar_one_or_none()

    if job_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job_model.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed jobs can be retried",
        )

    # Route the retry claim through the transition service (attempt
    # bookkeeping, parent re-projection), then re-enqueue through the outbox;
    # a crash between the two leaves a PENDING job the dispatch sweep recovers.
    try:
        await transition_job(db, job_model.id, JobStatus.PENDING)
    except InvalidTransitionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed jobs can be retried",
        )
    await enqueue_job(db, job_model.id, message="Queued for retry")
    await db.refresh(job_model)

    return _job_response(job_model)
