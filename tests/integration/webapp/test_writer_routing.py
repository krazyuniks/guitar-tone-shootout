"""Terminal-writer routing through the transition service (DOM-terminal-writer-routing).

Covers the retry bookkeeping (bounded auto-retry, ADR-0005), the retry
re-projection, parent-cancel semantics, the DLQ job-row coupling, and the
revived retry sweep.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.user import User
from webapp.services.job_transitions import (
    mark_job_dead_lettered,
    reconcile_parent,
    transition_job,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def _queues(db_session: AsyncSession) -> None:
    pgmq = PgmqClient(db_session)
    await pgmq.create_queue("shootout_commands")
    await pgmq.create_queue("audio_commands")


def _job(
    job_type: JobType = JobType.SHOOTOUT_AUDIO,
    status: JobStatus = JobStatus.RUNNING,
    *,
    user_id=None,
    parent_job_id=None,
    entity_id=None,
    attempt: int = 1,
) -> Job:
    return Job(
        id=uuid4(),
        user_id=user_id,
        job_type=job_type,
        parent_job_id=parent_job_id,
        entity_id=entity_id or uuid4(),
        status=status,
        progress=0,
        attempt=attempt,
        max_attempts=2,
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestRetryBookkeeping:
    async def test_failure_under_cap_schedules_auto_retry(self, db_session: AsyncSession) -> None:
        job = _job(status=JobStatus.RUNNING, attempt=1)
        db_session.add(job)
        await db_session.flush()

        await transition_job(db_session, job.id, JobStatus.FAILED, error="boom")

        assert job.next_retry_at is not None

    async def test_failure_at_cap_stays_failed_for_admin(self, db_session: AsyncSession) -> None:
        job = _job(status=JobStatus.RUNNING, attempt=2)
        db_session.add(job)
        await db_session.flush()

        await transition_job(db_session, job.id, JobStatus.FAILED, error="boom")

        assert job.next_retry_at is None
        assert job.status == JobStatus.FAILED

    async def test_self_managed_type_never_auto_retries(self, db_session: AsyncSession) -> None:
        job = _job(JobType.SOURCE_SYNC, JobStatus.RUNNING, attempt=1)
        db_session.add(job)
        await db_session.flush()

        await transition_job(db_session, job.id, JobStatus.FAILED, error="sync broke")

        assert job.next_retry_at is None

    async def test_retry_claim_consumes_attempt_and_clears_failure(
        self, db_session: AsyncSession
    ) -> None:
        job = _job(status=JobStatus.RUNNING, attempt=1)
        db_session.add(job)
        await db_session.flush()
        await transition_job(db_session, job.id, JobStatus.FAILED, error="boom")

        await transition_job(db_session, job.id, JobStatus.PENDING)

        assert job.attempt == 2
        assert job.error is None
        assert job.next_retry_at is None
        assert job.completed_at is None


@pytest.mark.asyncio
@pytest.mark.integration
class TestParentCancelAndReprojection:
    @pytest.fixture
    async def tree(self, db_session: AsyncSession, test_user: User) -> dict:
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Routing Shootout",
            status=ShootoutStatus.PROCESSING,
        )
        db_session.add(shootout)
        parent = _job(
            JobType.SHOOTOUT, JobStatus.RUNNING, user_id=test_user.id, entity_id=shootout.id
        )
        db_session.add(parent)
        children = [_job(user_id=test_user.id, parent_job_id=parent.id) for _ in range(2)]
        db_session.add_all(children)
        await db_session.flush()
        return {"shootout": shootout, "parent": parent, "children": children}

    async def test_parent_cancel_projects_shootout_failed(
        self, db_session: AsyncSession, tree: dict
    ) -> None:
        """Parent cancel blocks completion only; the projection reaches FAILED."""
        await transition_job(db_session, tree["parent"].id, JobStatus.CANCELLED)

        await db_session.refresh(tree["shootout"])
        assert tree["shootout"].status == ShootoutStatus.FAILED
        # In-flight children are not cascaded (v1).
        for child in tree["children"]:
            await db_session.refresh(child)
            assert child.status == JobStatus.RUNNING

    async def test_no_master_spawn_under_terminal_parent(
        self, db_session: AsyncSession, tree: dict
    ) -> None:
        """Children finishing under a cancelled parent are never published."""
        await transition_job(db_session, tree["parent"].id, JobStatus.CANCELLED)
        for child in tree["children"]:
            await db_session.execute(
                text("UPDATE core_jobs SET status = 'completed' WHERE id = :id"),
                {"id": str(child.id)},
            )

        await reconcile_parent(db_session, tree["parent"].id)
        await db_session.commit()

        master = (
            await db_session.execute(
                select(Job).where(
                    Job.parent_job_id == tree["parent"].id,
                    Job.job_type == JobType.SHOOTOUT_MASTER,
                )
            )
        ).scalar_one_or_none()
        assert master is None

    async def test_retry_reprojection_revives_failed_run(
        self, db_session: AsyncSession, tree: dict
    ) -> None:
        """A reclaimed failure brings the parent and shootout back to life."""
        child_a, child_b = tree["children"]
        await db_session.execute(
            text("UPDATE core_jobs SET status = 'completed' WHERE id = :id"),
            {"id": str(child_a.id)},
        )
        await transition_job(db_session, child_b.id, JobStatus.FAILED, error="boom")
        await db_session.refresh(tree["parent"])
        assert tree["parent"].status == JobStatus.FAILED

        await transition_job(db_session, child_b.id, JobStatus.PENDING)

        await db_session.refresh(tree["parent"])
        await db_session.refresh(tree["shootout"])
        assert tree["parent"].status == JobStatus.RUNNING
        assert tree["parent"].error is None
        assert tree["shootout"].status == ShootoutStatus.PROCESSING


@pytest.mark.asyncio
@pytest.mark.integration
class TestDeadLetterCoupling:
    async def test_dead_lettered_message_marks_job_row(self, db_session: AsyncSession) -> None:
        job = _job(status=JobStatus.RUNNING)
        db_session.add(job)
        await db_session.flush()

        await mark_job_dead_lettered(
            db_session,
            {"payload": {"job_id": str(job.id)}},
            "max retries exceeded",
        )

        await db_session.refresh(job)
        assert job.status == JobStatus.DEAD_LETTERED
        assert "max retries exceeded" in (job.error or "")

    async def test_completed_job_is_left_alone(self, db_session: AsyncSession) -> None:
        job = _job(status=JobStatus.RUNNING)
        db_session.add(job)
        await db_session.flush()
        await transition_job(db_session, job.id, JobStatus.COMPLETED)

        await mark_job_dead_lettered(
            db_session, {"payload": {"job_id": str(job.id)}}, "late redelivery"
        )

        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.integration
class TestRetrySweep:
    async def test_due_failed_job_is_reclaimed_and_enqueued(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import t3k_sync.tasks as tasks_mod

        job = _job(JobType.SHOOTOUT_AUDIO, JobStatus.RUNNING, attempt=1)
        db_session.add(job)
        await db_session.flush()
        await transition_job(db_session, job.id, JobStatus.FAILED, error="boom")
        # Make the retry due now.
        await db_session.execute(
            text("UPDATE core_jobs SET next_retry_at = now() - interval '1 minute' WHERE id = :id"),
            {"id": str(job.id)},
        )

        monkeypatch.setattr(tasks_mod, "_test_session", db_session)
        await tasks_mod.process_pending_retries()

        await db_session.refresh(job)
        assert job.status == JobStatus.QUEUED
        assert job.attempt == 2

        result = await db_session.execute(
            text(
                "SELECT message FROM pgmq.q_audio_commands "
                "WHERE message->'payload'->>'job_id' = :jid"
            ),
            {"jid": str(job.id)},
        )
        assert len(result.fetchall()) == 1
