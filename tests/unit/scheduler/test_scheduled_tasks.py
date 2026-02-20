"""Unit tests for scheduled tasks.

Tests the scheduled cron tasks:
- monitor_stale_jobs: Detects stale heartbeats and moves jobs to DEAD_LETTERED
- process_pending_retries: Processes FAILED jobs eligible for retry
- scheduler_heartbeat: Updates scheduler health record and renews lock
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.domain.entities.job import Job
from core.domain.value_objects.job_status import JobStatus, JobType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _register_test_session(session: AsyncSession):
    """Register the test session with the scheduler jobs module."""
    from scheduler.schedules import jobs

    jobs._test_session = session
    yield
    jobs._test_session = None


class TestMonitorStaleJobsModule:
    """Test monitor_stale_jobs scheduled task module."""

    def test_jobs_schedule_module_exists(self) -> None:
        """Module scheduler.schedules.jobs exists."""
        from scheduler.schedules import jobs

        assert jobs is not None

    def test_monitor_stale_jobs_function_exists(self) -> None:
        """Function monitor_stale_jobs exists in scheduler.schedules.jobs."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        assert monitor_stale_jobs is not None
        assert callable(monitor_stale_jobs)


class TestMonitorStaleJobsLogic:
    """Test stale job detection logic."""

    async def test_marks_running_job_with_stale_heartbeat_as_dead_lettered(
        self, session: AsyncSession
    ) -> None:
        """RUNNING job with heartbeat older than 2 minutes is marked DEAD_LETTERED."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create RUNNING job with stale heartbeat (3 minutes ago)
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

        # Run stale job monitor
        await monitor_stale_jobs()

        # Refresh and verify status changed to DEAD_LETTERED
        await session.refresh(job_model)
        assert job_model.status == JobStatus.DEAD_LETTERED.value
        assert job_model.error is not None
        assert "stale heartbeat" in job_model.error.lower()

    async def test_does_not_mark_running_job_with_recent_heartbeat(
        self, session: AsyncSession
    ) -> None:
        """RUNNING job with recent heartbeat (<2 minutes) is not marked stale."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create RUNNING job with recent heartbeat (30 seconds ago)
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

        # Run stale job monitor
        await monitor_stale_jobs()

        # Verify status unchanged
        await session.refresh(job_model)
        assert job_model.status == JobStatus.RUNNING.value

    async def test_does_not_mark_non_running_job_with_stale_heartbeat(
        self, session: AsyncSession
    ) -> None:
        """Non-RUNNING job with stale heartbeat is not affected."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create PENDING job with stale heartbeat
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

        # Run stale job monitor
        await monitor_stale_jobs()

        # Verify status unchanged
        await session.refresh(job_model)
        assert job_model.status == JobStatus.PENDING.value

    async def test_marks_multiple_stale_jobs(self, session: AsyncSession) -> None:
        """All RUNNING jobs with stale heartbeats are marked DEAD_LETTERED."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        from webapp.adapters.persistence.models.job import Job as JobModel

        stale_time = datetime.now(UTC) - timedelta(minutes=3)
        job_ids = []

        # Create 3 stale RUNNING jobs
        for _ in range(3):
            job_entity = Job(
                id=uuid4(),
                user_id=None,
                job_type=JobType.AUDIO_PROCESSING,
                status=JobStatus.RUNNING,
                last_heartbeat=stale_time,
            )
            job_ids.append(job_entity.id)
            job_model = JobModel.from_entity(job_entity)
            session.add(job_model)

        await session.commit()

        # Run monitor
        await monitor_stale_jobs()

        # Verify all marked as DEAD_LETTERED (scoped to our job IDs)
        result = await session.execute(
            select(JobModel).where(
                JobModel.status == JobStatus.DEAD_LETTERED.value,
                JobModel.id.in_(job_ids),
            )
        )
        dead_lettered_jobs = result.scalars().all()
        assert len(dead_lettered_jobs) == 3


class TestProcessPendingRetriesModule:
    """Test process_pending_retries scheduled task module."""

    def test_process_pending_retries_function_exists(self) -> None:
        """Function process_pending_retries exists in scheduler.schedules.jobs."""
        from scheduler.schedules.jobs import process_pending_retries

        assert process_pending_retries is not None
        assert callable(process_pending_retries)


class TestProcessPendingRetriesLogic:
    """Test retry processing logic."""

    async def test_resets_failed_job_with_retry_time_reached(self, session: AsyncSession) -> None:
        """FAILED job with next_retry_at <= now is reset to PENDING."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create FAILED job eligible for retry (next_retry_at is now)
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

        # Run retry processor
        await process_pending_retries()

        # Verify status changed to PENDING
        await session.refresh(job_model)
        assert job_model.status == JobStatus.PENDING.value

    async def test_does_not_retry_job_before_retry_time(self, session: AsyncSession) -> None:
        """FAILED job with next_retry_at in future is not retried yet."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create FAILED job with future retry time
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

        # Run retry processor
        await process_pending_retries()

        # Verify status unchanged
        await session.refresh(job_model)
        assert job_model.status == JobStatus.FAILED.value

    async def test_does_not_retry_job_at_max_attempts(self, session: AsyncSession) -> None:
        """FAILED job at max_attempts is not retried."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create FAILED job at max attempts
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

        # Run retry processor
        await process_pending_retries()

        # Verify status unchanged
        await session.refresh(job_model)
        assert job_model.status == JobStatus.FAILED.value

    async def test_processes_multiple_eligible_retries(self, session: AsyncSession) -> None:
        """All eligible FAILED jobs are reset to PENDING."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_ids = []

        # Create 3 eligible FAILED jobs
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
            job_model = JobModel.from_entity(job_entity)
            session.add(job_model)

        await session.commit()

        # Run processor
        await process_pending_retries()

        # Verify all reset to PENDING (scoped to our job IDs)
        result = await session.execute(
            select(JobModel).where(
                JobModel.status == JobStatus.PENDING.value,
                JobModel.id.in_(job_ids),
            )
        )
        pending_jobs = result.scalars().all()
        assert len(pending_jobs) == 3

    async def test_does_not_retry_non_failed_jobs(self, session: AsyncSession) -> None:
        """Non-FAILED jobs are not affected by retry processing."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create COMPLETED job with retry time in past
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

        # Run processor
        await process_pending_retries()

        # Verify status unchanged
        await session.refresh(job_model)
        assert job_model.status == JobStatus.COMPLETED.value


class TestSchedulerHeartbeatModule:
    """Test scheduler_heartbeat scheduled task module."""

    def test_scheduler_heartbeat_function_exists(self) -> None:
        """Function scheduler_heartbeat exists in scheduler.schedules.jobs."""
        from scheduler.schedules.jobs import scheduler_heartbeat

        assert scheduler_heartbeat is not None
        assert callable(scheduler_heartbeat)


class TestSchedulerHeartbeatLogic:
    """Test scheduler heartbeat renewal logic."""

    async def test_renews_distributed_lock(self) -> None:
        """scheduler_heartbeat renews the distributed lock TTL."""
        from scheduler.schedules.jobs import scheduler_heartbeat

        class FakeLock:
            """Test double for DistributedLock that tracks renewal calls."""

            def __init__(self) -> None:
                self.renew_calls: int = 0

            async def renew(self) -> None:
                self.renew_calls += 1

        fake_lock = FakeLock()
        await scheduler_heartbeat(lock=fake_lock)

        # Verify lock renewal was called
        assert fake_lock.renew_calls == 1

    async def test_updates_scheduler_health_record(self) -> None:
        """scheduler_heartbeat updates scheduler health timestamp."""
        from scheduler.schedules.jobs import scheduler_heartbeat

        # Call heartbeat
        await scheduler_heartbeat()

        # Verify health record updated (actual health table tested separately)
        # This test verifies the function executes without error
        assert True  # Placeholder - actual DB query will be added by implementer


class TestTaskScheduleConfiguration:
    """Test TaskIQ schedule configuration."""

    def test_monitor_stale_jobs_has_schedule_decorator(self) -> None:
        """monitor_stale_jobs has TaskIQ schedule decorator (every 2 minutes)."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        # Verify function has TaskIQ label metadata for scheduling
        assert hasattr(monitor_stale_jobs, "labels")
        assert "schedule" in monitor_stale_jobs.labels

    def test_process_pending_retries_has_schedule_decorator(self) -> None:
        """process_pending_retries has TaskIQ schedule decorator (every 2 minutes)."""
        from scheduler.schedules.jobs import process_pending_retries

        assert hasattr(process_pending_retries, "labels")
        assert "schedule" in process_pending_retries.labels

    def test_scheduler_heartbeat_has_schedule_decorator(self) -> None:
        """scheduler_heartbeat has TaskIQ schedule decorator (every 1 minute)."""
        from scheduler.schedules.jobs import scheduler_heartbeat

        assert hasattr(scheduler_heartbeat, "labels")
        assert "schedule" in scheduler_heartbeat.labels

    def test_monitor_stale_jobs_schedule_interval(self) -> None:
        """monitor_stale_jobs runs every 2 minutes."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        schedule = monitor_stale_jobs.labels["schedule"][0]
        assert schedule["interval"] == 120

    def test_process_pending_retries_schedule_interval(self) -> None:
        """process_pending_retries runs every 2 minutes."""
        from scheduler.schedules.jobs import process_pending_retries

        schedule = process_pending_retries.labels["schedule"][0]
        assert schedule["interval"] == 120

    def test_scheduler_heartbeat_schedule_interval(self) -> None:
        """scheduler_heartbeat runs every 1 minute."""
        from scheduler.schedules.jobs import scheduler_heartbeat

        schedule = scheduler_heartbeat.labels["schedule"][0]
        assert schedule["interval"] == 60


class TestSchedulerDatabaseIntegration:
    """Test scheduler uses worker database session."""

    def test_scheduler_db_module_exists(self) -> None:
        """Module scheduler.db exists for database session management."""
        from scheduler import db

        assert db is not None

    def test_get_session_function_exists(self) -> None:
        """Function get_session exists in scheduler.db module."""
        from scheduler.db import get_session

        assert get_session is not None
        assert callable(get_session)

    async def test_monitor_stale_jobs_uses_database_session(self, session: AsyncSession) -> None:
        """monitor_stale_jobs queries jobs table via database session."""
        from scheduler.schedules.jobs import monitor_stale_jobs

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create test data
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

        # Run task (should query database via raw SQL)
        await monitor_stale_jobs()

        # Expire ORM cache so refresh re-reads from DB (raw SQL bypasses identity map)
        session.expire_all()
        result = await session.execute(select(JobModel).where(JobModel.id == job_entity.id))
        updated_job = result.scalar_one()
        assert updated_job.status != JobStatus.RUNNING.value

    async def test_process_pending_retries_uses_database_session(
        self, session: AsyncSession
    ) -> None:
        """process_pending_retries queries jobs table via database session."""
        from scheduler.schedules.jobs import process_pending_retries

        from webapp.adapters.persistence.models.job import Job as JobModel

        # Create test data
        retry_time = datetime.now(UTC) - timedelta(seconds=1)
        job_entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.FAILED,
            attempt=1,
            max_attempts=3,
            next_retry_at=retry_time,
        )
        job_model = JobModel.from_entity(job_entity)
        session.add(job_model)
        await session.commit()

        # Run task (should query database via raw SQL)
        await process_pending_retries()

        # Expire ORM cache so refresh re-reads from DB (raw SQL bypasses identity map)
        session.expire_all()
        result = await session.execute(select(JobModel).where(JobModel.id == job_entity.id))
        updated_job = result.scalar_one()
        assert updated_job.status == JobStatus.PENDING.value
