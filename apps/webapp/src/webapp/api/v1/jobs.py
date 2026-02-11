"""Job API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.job import JobResponse
from webapp.services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session or None to clear
    """
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing.

    Args:
        user: Test user to use as CurrentUser or None to clear
    """
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    Checks for test session override first, then falls back to the
    global database session factory.
    """
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


async def get_current_user() -> User:
    """Get current authenticated user dependency.

    In production this would validate session/token.
    For testing, uses override if set.
    """
    if _user_override:
        return _user_override
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: str | None = Query(None, alias="status"),
    job_type: str | None = Query(None, alias="job_type"),
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

    # Parse filters
    status_enum = JobStatus(status_filter) if status_filter else None
    job_type_enum = JobType(job_type) if job_type else None

    jobs = await service.get_by_user_id(
        current_user.id,
        status=status_enum,
        job_type=job_type_enum,
    )

    return [
        JobResponse(
            id=job.id,
            user_id=job.user_id,
            job_type=job.job_type.value,
            status=job.status.value,
            progress=job.progress,
            message=job.message,
            error=job.error,
            result_path=job.result_path,
            entity_id=job.entity_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
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

    job = await service.get_by_id(job_id)

    # Return 404 if job not found or not owned by user
    # (Return 404 instead of 403 to avoid leaking existence)
    if not job or job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        error=job.error,
        result_path=job.result_path,
        entity_id=job.entity_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
