"""Job management API endpoints.

Provides CRUD operations for background processing jobs:
- POST /jobs - Create a new job
- GET /jobs - List user's jobs with filtering
- GET /jobs/{id} - Get job details
- DELETE /jobs/{id} - Cancel a job
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.job import JobStatus
from app.schemas.job import JobCreate, JobListResponse, JobResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_in: JobCreate,
    user: CurrentUser,
    db: DbSession,
) -> JobResponse:
    """Create a new processing job.

    The job will be created in PENDING status and queued for processing.

    Args:
        job_in: Job configuration.
        user: Current authenticated user.
        db: Database session.

    Returns:
        The created job.
    """
    service = JobService(db)
    job = await service.create_job(user, job_in)

    # TODO: Queue the job for processing via TaskIQ
    # from app.tasks.shootout import process_shootout_task
    # await process_shootout_task.kiq(str(job.id), job_in.config)

    return JobResponse.model_validate(job)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    user: CurrentUser,
    db: DbSession,
    status_filter: JobStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> JobListResponse:
    """List jobs for the current user.

    Args:
        user: Current authenticated user.
        db: Database session.
        status_filter: Optional status filter.
        page: Page number (1-indexed).
        page_size: Items per page (1-100).

    Returns:
        Paginated list of jobs.
    """
    service = JobService(db)
    jobs, total = await service.list_jobs(user, status_filter, page, page_size)

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> JobResponse:
    """Get details of a specific job.

    Args:
        job_id: The job ID.
        user: Current authenticated user.
        db: Database session.

    Returns:
        The job details.

    Raises:
        HTTPException: If job not found or doesn't belong to user.
    """
    service = JobService(db)
    job = await service.get_job(user, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Cancel a pending, queued, or running job.

    Args:
        job_id: The job ID to cancel.
        user: Current authenticated user.
        db: Database session.

    Raises:
        HTTPException: If job not found or cannot be cancelled.
    """
    service = JobService(db)
    job = await service.cancel_job(user, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or cannot be cancelled",
        )
