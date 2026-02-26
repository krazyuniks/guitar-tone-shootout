"""Unit tests for t3k_sync scheduled tasks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from gts.domain.entities.job import Job
from gts.domain.value_objects.job_status import JobStatus, JobType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestMonitorStaleJobs:
    """Test monitor_stale_jobs scheduled task."""

    async def test_marks_running_job_with_stale_heartbeat_as_dead_lettered(
        self, session: AsyncSession
    ) -> None:
        """RUNNING job with heartbeat older than 2 minutes is marked DEAD_LETTERED."""
        from t3k_sync.tasks import monitor_stale_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        stale_time = datetime.now(UTC) - timedelta(minutes=3)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.RUNNING,
            last_heartbeat=stale_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await monitor_stale_jobs()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.DEAD_LETTERED.value
        assert job_model.error is not None
        assert "stale heartbeat" in job_model.error.lower()

    async def test_does_not_mark_running_job_with_recent_heartbeat(
        self, session: AsyncSession
    ) -> None:
        """RUNNING job with recent heartbeat (<2 minutes) is not marked stale."""
        from t3k_sync.tasks import monitor_stale_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        recent_time = datetime.now(UTC) - timedelta(seconds=30)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.RUNNING,
            last_heartbeat=recent_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await monitor_stale_jobs()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.RUNNING.value

    async def test_does_not_mark_non_running_job_with_stale_heartbeat(
        self, session: AsyncSession
    ) -> None:
        """Non-RUNNING job with stale heartbeat is not affected."""
        from t3k_sync.tasks import monitor_stale_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        stale_time = datetime.now(UTC) - timedelta(minutes=3)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.PENDING,
            last_heartbeat=stale_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await monitor_stale_jobs()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.PENDING.value

    async def test_marks_multiple_stale_jobs(self, session: AsyncSession) -> None:
        """All RUNNING jobs with stale heartbeats are marked DEAD_LETTERED."""
        from t3k_sync.tasks import monitor_stale_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        stale_time = datetime.now(UTC) - timedelta(minutes=3)
        job_ids = []

        for _ in range(3):
            job_entity = Job(
                id=uuid4(),
                user_id=None,
                job_type=JobType.AUDIO_PROCESSING,
                status=JobStatus.RUNNING,
                last_heartbeat=stale_time,
            )
            job_ids.append(job_entity.id)
            session.add(JobModel.from_entity(job_entity))

        await session.commit()

        await monitor_stale_jobs()

        result = await session.execute(
            select(JobModel).where(
                JobModel.status == JobStatus.DEAD_LETTERED.value,
                JobModel.id.in_(job_ids),
            )
        )
        assert len(result.scalars().all()) == 3


class TestProcessPendingRetries:
    """Test process_pending_retries scheduled task."""

    async def test_resets_failed_job_with_retry_time_reached(self, session: AsyncSession) -> None:
        """FAILED job with next_retry_at <= now is reset to PENDING."""
        from t3k_sync.tasks import process_pending_retries
        from webapp.adapters.persistence.models.job import Job as JobModel

        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            attempt=1,
            max_attempts=3,
            next_retry_at=retry_time,
            error="Previous failure",
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await process_pending_retries()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.PENDING.value

    async def test_does_not_retry_job_before_retry_time(self, session: AsyncSession) -> None:
        """FAILED job with next_retry_at in future is not retried yet."""
        from t3k_sync.tasks import process_pending_retries
        from webapp.adapters.persistence.models.job import Job as JobModel

        future_time = datetime.now(UTC) + timedelta(minutes=5)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            attempt=1,
            max_attempts=3,
            next_retry_at=future_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await process_pending_retries()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.FAILED.value

    async def test_does_not_retry_job_at_max_attempts(self, session: AsyncSession) -> None:
        """FAILED job at max_attempts is not retried."""
        from t3k_sync.tasks import process_pending_retries
        from webapp.adapters.persistence.models.job import Job as JobModel

        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            attempt=3,
            max_attempts=3,
            next_retry_at=retry_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await process_pending_retries()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.FAILED.value

    async def test_processes_multiple_eligible_retries(self, session: AsyncSession) -> None:
        """All eligible FAILED jobs are reset to PENDING."""
        from t3k_sync.tasks import process_pending_retries
        from webapp.adapters.persistence.models.job import Job as JobModel

        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_ids = []

        for _ in range(3):
            job_entity = Job(
                id=uuid4(),
                user_id=None,
                job_type=JobType.AUDIO_PROCESSING,
                status=JobStatus.FAILED,
                attempt=1,
                max_attempts=3,
                next_retry_at=retry_time,
            )
            job_ids.append(job_entity.id)
            session.add(JobModel.from_entity(job_entity))

        await session.commit()

        await process_pending_retries()

        result = await session.execute(
            select(JobModel).where(
                JobModel.status == JobStatus.PENDING.value,
                JobModel.id.in_(job_ids),
            )
        )
        assert len(result.scalars().all()) == 3

    async def test_does_not_retry_non_failed_jobs(self, session: AsyncSession) -> None:
        """Non-FAILED jobs are not affected by retry processing."""
        from t3k_sync.tasks import process_pending_retries
        from webapp.adapters.persistence.models.job import Job as JobModel

        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.COMPLETED,
            next_retry_at=retry_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        await process_pending_retries()

        await session.refresh(job_model)
        assert job_model.status == JobStatus.COMPLETED.value
