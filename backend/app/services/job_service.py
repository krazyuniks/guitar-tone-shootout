"""Job service for managing background processing jobs."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.job import JobCreate


class JobService:
    """Service layer for Job CRUD operations."""

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session."""
        self.db = db

    async def create_job(self, user: User, job_in: JobCreate) -> Job:
        """Create a new job for the user.

        Args:
            user: The authenticated user creating the job.
            job_in: Job creation data.

        Returns:
            The created Job instance.
        """
        job = Job(
            user_id=user.id,
            status=JobStatus.PENDING,
            progress=0,
            config=json.dumps(job_in.config),
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_job(self, user: User, job_id: UUID) -> Job | None:
        """Get a job by ID, ensuring it belongs to the user.

        Args:
            user: The authenticated user.
            job_id: The job ID to retrieve.

        Returns:
            The Job if found and owned by user, None otherwise.
        """
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        user: User,
        status: JobStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """List jobs for a user with optional filtering.

        Args:
            user: The authenticated user.
            status: Optional status filter.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (jobs list, total count).
        """
        # Build base query
        query = select(Job).where(Job.user_id == user.id)
        count_query = (
            select(func.count()).select_from(Job).where(Job.user_id == user.id)
        )

        if status:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        jobs = list(result.scalars().all())

        return jobs, total

    async def cancel_job(self, user: User, job_id: UUID) -> Job | None:
        """Cancel a pending or queued job.

        Args:
            user: The authenticated user.
            job_id: The job ID to cancel.

        Returns:
            The cancelled Job if successful, None if not found or not cancellable.
        """
        job = await self.get_job(user, job_id)
        if not job:
            return None

        # Can only cancel pending or queued jobs
        if job.status not in (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING):
            return None

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(UTC)
        job.message = "Cancelled by user"
        await self.db.flush()
        await self.db.refresh(job)

        # TODO: If job is running, send cancellation signal via TaskIQ

        return job

    async def update_job_progress(
        self,
        job_id: UUID,
        status: JobStatus,
        progress: int,
        message: str | None = None,
    ) -> Job | None:
        """Update job progress (called by workers).

        Args:
            job_id: The job ID to update.
            status: New status.
            progress: Progress percentage (0-100).
            message: Optional status message.

        Returns:
            The updated Job if found, None otherwise.
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return None

        job.status = status
        job.progress = progress
        job.message = message

        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(UTC)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def complete_job(
        self,
        job_id: UUID,
        result_path: str,
    ) -> Job | None:
        """Mark job as completed with result path.

        Args:
            job_id: The job ID to complete.
            result_path: Path to the job results.

        Returns:
            The completed Job if found, None otherwise.
        """
        return await self.update_job_progress(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Completed successfully",
        )

    async def fail_job(
        self,
        job_id: UUID,
        error: str,
    ) -> Job | None:
        """Mark job as failed with error message.

        Args:
            job_id: The job ID to fail.
            error: Error message.

        Returns:
            The failed Job if found, None otherwise.
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return None

        job.status = JobStatus.FAILED
        job.progress = job.progress  # Keep current progress
        job.error = error
        job.completed_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(job)
        return job
