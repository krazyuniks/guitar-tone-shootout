"""JobService for querying and managing jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.domain.entities.job import Job


class JobService:
    """Service for querying and managing jobs.

    Handles job status queries and user filtering.
    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = SQLAlchemyJobRepository(session)

    async def get_by_id(self, job_id: UUID) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job entity if found, None otherwise
        """
        return await self.repository.get_by_id(job_id)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """Get jobs for a user, optionally filtered.

        Args:
            user_id: User ID to filter by
            status: Optional status filter
            job_type: Optional job type filter
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of Job entities
        """
        return await self.repository.get_by_user_id(
            user_id,
            status=status,
            job_type=job_type,
            limit=limit,
            offset=offset,
        )

    async def get_active_by_user_id(self, user_id: UUID) -> list[Job]:
        """Get active (non-terminal) jobs for a user.

        Args:
            user_id: User ID to filter by

        Returns:
            List of active Job entities
        """
        return await self.repository.get_active_by_user_id(user_id)

    async def count_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
    ) -> int:
        """Count jobs for a user, optionally filtered by status.

        Args:
            user_id: User ID to filter by
            status: Optional status filter

        Returns:
            Count of matching jobs
        """
        return await self.repository.count_by_user_id(user_id, status=status)

    async def get_by_entity_id(self, entity_id: UUID) -> list[Job]:
        """Get all jobs for a specific entity.

        Args:
            entity_id: Entity ID to filter by

        Returns:
            List of Job entities for this entity
        """
        return await self.repository.get_by_entity_id(entity_id)
