"""SQLAlchemy implementation of JobRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from core.domain.entities.job import Job as JobEntity
from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyJobRepository:
    """SQLAlchemy implementation of JobRepository protocol.

    Maps between domain Job entities and ORM Job models.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, job_id: UUID) -> JobEntity | None:
        """Get a job by its ID.

        Args:
            job_id: The job's UUID

        Returns:
            The Job entity if found, None otherwise
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        return self._to_entity(job)

    async def get_by_task_id(self, task_id: str) -> JobEntity | None:
        """Get a job by its TaskIQ task ID.

        Args:
            task_id: The TaskIQ task ID

        Returns:
            The Job entity if found, None otherwise
        """
        stmt = select(Job).where(Job.task_id == task_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        return self._to_entity(job)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobEntity]:
        """Get jobs for a user, optionally filtered.

        Args:
            user_id: The owner's UUID
            status: Optional status filter
            job_type: Optional type filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Jobs ordered by created_at desc
        """
        stmt = select(Job).where(Job.user_id == user_id)

        if status is not None:
            stmt = stmt.where(Job.status == status)
        if job_type is not None:
            stmt = stmt.where(Job.type == job_type)

        stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [self._to_entity(job) for job in jobs]

    async def get_by_entity_id(self, entity_id: UUID) -> list[JobEntity]:
        """Get jobs for an entity.

        Args:
            entity_id: The entity's UUID

        Returns:
            List of Jobs for this entity
        """
        stmt = select(Job).where(Job.entity_id == entity_id).order_by(Job.created_at.desc())
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [self._to_entity(job) for job in jobs]

    async def get_active_by_user_id(self, user_id: UUID) -> list[JobEntity]:
        """Get active (non-terminal) jobs for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            List of active Jobs
        """
        # Active statuses: pending, queued, running
        active_statuses = [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]

        stmt = (
            select(Job)
            .where(Job.user_id == user_id)
            .where(Job.status.in_(active_statuses))
            .order_by(Job.created_at.desc())
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [self._to_entity(job) for job in jobs]

    async def get_children(self, parent_job_id: UUID) -> list[JobEntity]:
        """Get child jobs for a parent job.

        Args:
            parent_job_id: The parent job's UUID

        Returns:
            List of child Jobs
        """
        stmt = (
            select(Job)
            .where(Job.parent_job_id == parent_job_id)
            .order_by(Job.created_at.asc())
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [self._to_entity(job) for job in jobs]

    async def count_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
    ) -> int:
        """Count jobs for a user, optionally filtered by status.

        Args:
            user_id: The owner's UUID
            status: Optional status filter

        Returns:
            The count of matching jobs
        """
        stmt = select(func.count()).select_from(Job).where(Job.user_id == user_id)

        if status is not None:
            stmt = stmt.where(Job.status == status)

        result = await self.session.execute(stmt)
        count = result.scalar()
        return count or 0

    async def get_pending_for_retry(self, limit: int = 10) -> list[JobEntity]:
        """Get pending jobs that are ready for retry.

        Args:
            limit: Maximum number of results

        Returns:
            List of Jobs ready for retry
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .where(
                or_(
                    Job.next_retry_at.is_(None),
                    Job.next_retry_at <= now,
                )
            )
            .order_by(Job.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [self._to_entity(job) for job in jobs]

    async def save(self, job: JobEntity) -> None:
        """Save a job (create or update).

        Args:
            job: The job to save
        """
        # Check if job exists
        stmt = select(Job).where(Job.id == job.id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new job
            orm_job = Job(
                id=job.id,
                user_id=job.user_id,
                job_type=job.job_type,
                parent_job_id=job.parent_job_id,
                depends_on=[str(dep) for dep in job.depends_on],
                status=job.status,
                progress=job.progress,
                message=job.message,
                started_at=job.started_at,
                completed_at=job.completed_at,
                last_heartbeat=job.last_heartbeat,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                next_retry_at=job.next_retry_at,
                result_path=job.result_path,
                error=job.error,
                task_id=job.task_id,
                entity_id=job.entity_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            self.session.add(orm_job)
        else:
            # Update existing job
            existing.user_id = job.user_id
            existing.job_type = job.job_type
            existing.parent_job_id = job.parent_job_id
            existing.depends_on = [str(dep) for dep in job.depends_on]
            existing.status = job.status
            existing.progress = job.progress
            existing.message = job.message
            existing.started_at = job.started_at
            existing.completed_at = job.completed_at
            existing.last_heartbeat = job.last_heartbeat
            existing.attempt = job.attempt
            existing.max_attempts = job.max_attempts
            existing.next_retry_at = job.next_retry_at
            existing.result_path = job.result_path
            existing.error = job.error
            existing.task_id = job.task_id
            existing.entity_id = job.entity_id
            existing.updated_at = job.updated_at

        await self.session.flush()

    async def delete(self, job_id: UUID) -> None:
        """Delete a job by ID.

        Args:
            job_id: The job's UUID
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if job is not None:
            await self.session.delete(job)
            await self.session.flush()

    def _to_entity(self, orm_job: Job) -> JobEntity:
        """Convert ORM Job to domain entity.

        Args:
            orm_job: ORM Job model

        Returns:
            Domain Job entity
        """
        from uuid import UUID as PyUUID

        return JobEntity(
            id=orm_job.id,
            user_id=orm_job.user_id,
            job_type=orm_job.job_type,
            parent_job_id=orm_job.parent_job_id,
            depends_on=[PyUUID(dep) for dep in (orm_job.depends_on or [])],
            status=orm_job.status,
            progress=orm_job.progress,
            message=orm_job.message,
            started_at=orm_job.started_at,
            completed_at=orm_job.completed_at,
            last_heartbeat=orm_job.last_heartbeat,
            attempt=orm_job.attempt,
            max_attempts=orm_job.max_attempts,
            next_retry_at=orm_job.next_retry_at,
            result_path=orm_job.result_path,
            error=orm_job.error,
            task_id=orm_job.task_id,
            entity_id=orm_job.entity_id,
            created_at=orm_job.created_at,
            updated_at=orm_job.updated_at,
        )
