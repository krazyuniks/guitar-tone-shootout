"""Shootout Processing Orchestrator Job Handler.

This module provides the SHOOTOUT job handler that orchestrates
processing of a shootout by creating child SHOOTOUT_AUDIO jobs
for each chain in the shootout.
"""

import os
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from worker.db import get_session
from worker.main import broker


@broker.task
async def handle_shootout_job(job_id: UUID) -> None:
    """Handle SHOOTOUT job by creating child SHOOTOUT_AUDIO jobs for each chain.

    This is the parent orchestrator job. It:
    1. Loads the parent job and shootout with all chains
    2. Updates shootout status to RUNNING
    3. Creates one SHOOTOUT_AUDIO child job per chain
    4. Commits all changes

    Args:
        job_id: The ID of the parent SHOOTOUT job

    Raises:
        ValueError: If job or shootout is not found
    """
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")

    async with get_session(database_url) as session:
        # Load parent job
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        parent_job = result.scalar_one_or_none()

        if parent_job is None:
            raise ValueError(f"Job {job_id} not found")

        shootout_id = parent_job.entity_id
        if shootout_id is None:
            raise ValueError(f"Job {job_id} has no entity_id set")

        # Load shootout with all chains
        stmt = (
            select(Shootout).where(Shootout.id == shootout_id).options(joinedload(Shootout.chains))
        )
        result = await session.execute(stmt)
        shootout = result.unique().scalar_one_or_none()

        if shootout is None:
            raise ValueError(f"Shootout {shootout_id} not found")

        # Update shootout status to RUNNING
        shootout.status = ShootoutStatus.RUNNING

        # Create one SHOOTOUT_AUDIO child job per chain
        for chain in shootout.chains:
            child_job = Job(
                user_id=parent_job.user_id,
                job_type=JobType.SHOOTOUT_AUDIO,
                parent_job_id=parent_job.id,
                entity_id=chain.id,
                status=JobStatus.PENDING,
            )
            session.add(child_job)

        await session.commit()


async def _update_parent_progress(parent_job_id: UUID, database_url: str) -> None:
    """Update parent job progress based on child completion.

    Args:
        parent_job_id: The parent job ID
        database_url: Database connection string
    """
    async with get_session(database_url) as session:
        stmt = select(Job).where(Job.id == parent_job_id)
        result = await session.execute(stmt)
        parent_job = result.scalar_one_or_none()

        if parent_job is None:
            return

        stmt = select(Job).where(Job.parent_job_id == parent_job_id)
        result = await session.execute(stmt)
        children = result.scalars().all()

        if not children:
            return

        completed_count = sum(1 for j in children if j.status == JobStatus.COMPLETED)
        total_count = len(children)
        progress = int((completed_count / total_count) * 100)

        parent_job.progress = progress

        all_completed = all(j.status == JobStatus.COMPLETED for j in children)
        any_failed = any(j.status == JobStatus.FAILED for j in children)

        if all_completed or any_failed:
            stmt = select(Shootout).where(Shootout.id == parent_job.entity_id)
            result = await session.execute(stmt)
            shootout = result.scalar_one_or_none()

            if shootout:
                if all_completed:
                    shootout.status = ShootoutStatus.COMPLETED
                elif any_failed:
                    shootout.status = ShootoutStatus.FAILED

        await session.commit()
