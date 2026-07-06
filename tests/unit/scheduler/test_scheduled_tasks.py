"""Unit tests for t3k_sync scheduled tasks."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, text

from gts.domain.entities.job import Job
from gts.domain.value_objects.job_status import JobStatus, JobType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestMonitorStaleJobs:
    """Test monitor_stale_jobs scheduled task."""

    async def test_reaps_running_job_with_stale_lease_as_failed(
        self, session: AsyncSession
    ) -> None:
        """A stale lease reaps as an ordinary FAILED (retryable), never a raw dead-letter."""
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
        assert job_model.status == JobStatus.FAILED.value
        assert job_model.error is not None
        assert "stale lease" in job_model.error.lower()
        # A first-attempt reap participates in bounded auto-retry.
        assert job_model.next_retry_at is not None

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
        """All RUNNING jobs with stale leases are reaped to FAILED."""
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
                JobModel.status == JobStatus.FAILED.value,
                JobModel.id.in_(job_ids),
            )
        )
        assert len(result.scalars().all()) == 3


class TestProcessPendingRetries:
    """Test process_pending_retries scheduled task."""

    async def test_resets_failed_job_with_retry_time_reached(self, session: AsyncSession) -> None:
        """FAILED job with next_retry_at <= now is reclaimed and enqueued (QUEUED)."""
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
        assert job_model.status == JobStatus.QUEUED.value
        assert job_model.attempt == 2

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
        """All eligible FAILED jobs are reclaimed and enqueued."""
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
                JobModel.status == JobStatus.QUEUED.value,
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


class TestPurgePgmqArchives:
    """Test purge_pgmq_archives scheduled task."""

    async def test_deletes_old_archive_rows(self, session: AsyncSession) -> None:
        """Archive rows older than the retention window are deleted."""
        from t3k_sync.tasks import purge_pgmq_archives

        # Create a dedicated test queue (transactional DDL — rolled back after test).
        await session.execute(text("SELECT pgmq.create('purge_test_q')"))
        await session.execute(text("SELECT pgmq.send('purge_test_q', '{}'::jsonb)"))
        msg_result = await session.execute(
            text("SELECT msg_id FROM pgmq.read('purge_test_q', 30, 1)")
        )
        msg_id = msg_result.scalar_one()
        await session.execute(
            text("SELECT pgmq.archive('purge_test_q', CAST(:msg_id AS bigint))"),
            {"msg_id": msg_id},
        )
        # Backdate to 31 days ago (beyond the 30-day default window).
        await session.execute(
            text("UPDATE pgmq.a_purge_test_q SET archived_at = :old_time"),
            {"old_time": datetime.now(UTC) - timedelta(days=31)},
        )

        prev_env = os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
        try:
            os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = "30"
            await purge_pgmq_archives()
        finally:
            if prev_env is None:
                os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
            else:
                os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = prev_env

        count = await session.execute(text("SELECT COUNT(*) FROM pgmq.a_purge_test_q"))
        assert count.scalar_one() == 0

    async def test_keeps_recent_archive_rows(self, session: AsyncSession) -> None:
        """Archive rows within the retention window are not deleted."""
        from t3k_sync.tasks import purge_pgmq_archives

        await session.execute(text("SELECT pgmq.create('purge_recent_q')"))
        await session.execute(text("SELECT pgmq.send('purge_recent_q', '{}'::jsonb)"))
        msg_result = await session.execute(
            text("SELECT msg_id FROM pgmq.read('purge_recent_q', 30, 1)")
        )
        msg_id = msg_result.scalar_one()
        await session.execute(
            text("SELECT pgmq.archive('purge_recent_q', CAST(:msg_id AS bigint))"),
            {"msg_id": msg_id},
        )
        # archived_at defaults to now() — well within 30-day window.

        prev_env = os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
        try:
            os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = "30"
            await purge_pgmq_archives()
        finally:
            if prev_env is None:
                os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
            else:
                os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = prev_env

        count = await session.execute(text("SELECT COUNT(*) FROM pgmq.a_purge_recent_q"))
        assert count.scalar_one() == 1

    async def test_no_error_when_no_archive_tables(self, session: AsyncSession) -> None:
        """Function completes without error when no pgmq archive tables exist."""
        from t3k_sync.tasks import purge_pgmq_archives

        # Rely on the fact that whatever tables exist will have no rows old enough
        # with a very short retention — just verify it doesn't raise.
        prev_env = os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
        try:
            os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = "36500"  # 100 years — deletes nothing
            await purge_pgmq_archives()
        finally:
            if prev_env is None:
                os.environ.pop("PGMQ_ARCHIVE_RETENTION_DAYS", None)
            else:
                os.environ["PGMQ_ARCHIVE_RETENTION_DAYS"] = prev_env


class TestPurgeOldJobs:
    """Test purge_old_jobs scheduled task."""

    async def test_deletes_old_terminal_jobs(self, session: AsyncSession) -> None:
        """Completed/failed/dead-lettered jobs older than the retention window are deleted."""
        from t3k_sync.tasks import purge_old_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        old_time = datetime.now(UTC) - timedelta(days=91)
        job_ids = []
        for status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTERED):
            entity = Job(
                id=uuid4(),
                user_id=None,
                job_type=JobType.AUDIO_PROCESSING,
                status=status,
                completed_at=old_time,
            )
            job_ids.append(entity.id)
            session.add(JobModel.from_entity(entity))
        await session.commit()

        prev_env = os.environ.pop("JOB_RETENTION_DAYS", None)
        try:
            os.environ["JOB_RETENTION_DAYS"] = "90"
            await purge_old_jobs()
        finally:
            if prev_env is None:
                os.environ.pop("JOB_RETENTION_DAYS", None)
            else:
                os.environ["JOB_RETENTION_DAYS"] = prev_env

        result = await session.execute(select(JobModel).where(JobModel.id.in_(job_ids)))
        assert result.scalars().all() == []

    async def test_keeps_recent_terminal_jobs(self, session: AsyncSession) -> None:
        """Terminal jobs within the retention window are not deleted."""
        from t3k_sync.tasks import purge_old_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        recent_time = datetime.now(UTC) - timedelta(days=10)
        entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.COMPLETED,
            completed_at=recent_time,
        )
        model = JobModel.from_entity(entity)
        session.add(model)
        await session.commit()

        prev_env = os.environ.pop("JOB_RETENTION_DAYS", None)
        try:
            os.environ["JOB_RETENTION_DAYS"] = "90"
            await purge_old_jobs()
        finally:
            if prev_env is None:
                os.environ.pop("JOB_RETENTION_DAYS", None)
            else:
                os.environ["JOB_RETENTION_DAYS"] = prev_env

        await session.refresh(model)
        assert model.status == JobStatus.COMPLETED.value

    async def test_does_not_delete_active_jobs(self, session: AsyncSession) -> None:
        """PENDING and RUNNING jobs are never deleted regardless of age."""
        from t3k_sync.tasks import purge_old_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        old_time = datetime.now(UTC) - timedelta(days=91)
        job_ids = []
        for status in (JobStatus.PENDING, JobStatus.RUNNING):
            entity = Job(
                id=uuid4(),
                user_id=None,
                job_type=JobType.AUDIO_PROCESSING,
                status=status,
                completed_at=old_time,
            )
            job_ids.append(entity.id)
            session.add(JobModel.from_entity(entity))
        await session.commit()

        prev_env = os.environ.pop("JOB_RETENTION_DAYS", None)
        try:
            os.environ["JOB_RETENTION_DAYS"] = "90"
            await purge_old_jobs()
        finally:
            if prev_env is None:
                os.environ.pop("JOB_RETENTION_DAYS", None)
            else:
                os.environ["JOB_RETENTION_DAYS"] = prev_env

        result = await session.execute(select(JobModel).where(JobModel.id.in_(job_ids)))
        assert len(result.scalars().all()) == 2

    async def test_does_not_delete_jobs_without_completed_at(self, session: AsyncSession) -> None:
        """Terminal jobs with NULL completed_at are not deleted."""
        from t3k_sync.tasks import purge_old_jobs
        from webapp.adapters.persistence.models.job import Job as JobModel

        entity = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.AUDIO_PROCESSING,
            status=JobStatus.COMPLETED,
            completed_at=None,
        )
        model = JobModel.from_entity(entity)
        session.add(model)
        await session.commit()

        prev_env = os.environ.pop("JOB_RETENTION_DAYS", None)
        try:
            os.environ["JOB_RETENTION_DAYS"] = "0"
            await purge_old_jobs()
        finally:
            if prev_env is None:
                os.environ.pop("JOB_RETENTION_DAYS", None)
            else:
                os.environ["JOB_RETENTION_DAYS"] = prev_env

        await session.refresh(model)
        assert model.status == JobStatus.COMPLETED.value
