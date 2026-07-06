"""Single-writer job transition service (docs/design/job-system-contract.md).

This module is the sole writer of Job.status and, via projection, of
Shootout.status; a structural guard test pins the shrinking allowlist of
not-yet-migrated legacy writers. Every move is validated against the
transition table (JobStatus.can_transition_to); a terminal move on a
SHOOTOUT_AUDIO child reconciles the parent shootout in the same transaction.
Lock order, always: own job row -> parent job row -> shootout row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.services.job_dispatch import enqueue_job

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

#: Terminal states that project the parent shootout to FAILED. CANCELLED maps
#: publicly to FAILED; the public lifecycle has five states, never more.
FAILED_CLASS = frozenset({JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTERED})


class TransitionError(Exception):
    """Base for transition failures."""


class JobNotFoundForTransitionError(TransitionError):
    """The job row does not exist."""


class InvalidTransitionError(TransitionError):
    """The requested move is not an edge of the transition table."""

    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition {current.value} -> {target.value}")


async def transition_job(
    session: AsyncSession,
    job_id: UUID,
    to_status: JobStatus,
    *,
    error: str | None = None,
    message: str | None = None,
) -> Job:
    """Move a job to `to_status`, reconcile its parent if terminal, and commit.

    Locks the job row, validates the move against the transition table (an
    invalid move raises before anything is written - a rejected no-op, never a
    half-write), applies bookkeeping, and for a terminal SHOOTOUT_AUDIO child
    re-projects the parent shootout inside the same transaction. The service
    owns its commit; callers never commit around it.
    """
    stmt = select(Job).where(Job.id == job_id).with_for_update()
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundForTransitionError(f"Job {job_id} not found")
    if not job.status.can_transition_to(to_status):
        raise InvalidTransitionError(job.status, to_status)

    now = datetime.now(UTC)
    job.status = to_status
    if message is not None:
        job.message = message
    if error is not None:
        job.error = error
    if to_status == JobStatus.RUNNING:
        if job.started_at is None:
            job.started_at = now
        job.last_heartbeat = now
    if to_status.is_terminal():
        job.completed_at = now

    if (
        to_status.is_terminal()
        and job.job_type == JobType.SHOOTOUT_AUDIO
        and job.parent_job_id is not None
    ):
        await reconcile_parent(session, job.parent_job_id)

    await session.commit()
    return job


async def reconcile_parent(session: AsyncSession, parent_job_id: UUID) -> None:
    """Project SHOOTOUT_AUDIO child states onto the parent job and shootout.

    Counting is closed over the whole terminal set: every terminal child lands
    in exactly one bucket (COMPLETED, or the FAILED_CLASS), so no terminal path
    can strand the projection in PROCESSING. Runs inside the caller's
    transaction and does not commit; the transition service (or the session
    wrapper in shootout_reconciliation) owns the commit.
    """
    parent_stmt = select(Job).where(Job.id == parent_job_id).with_for_update()
    parent_result = await session.execute(parent_stmt)
    parent_job = parent_result.scalar_one_or_none()
    if parent_job is None or parent_job.entity_id is None:
        return

    shootout_stmt = select(Shootout).where(Shootout.id == parent_job.entity_id).with_for_update()
    shootout_result = await session.execute(shootout_stmt)
    shootout = shootout_result.scalar_one_or_none()

    child_stmt = select(Job).where(
        Job.parent_job_id == parent_job_id,
        Job.job_type == JobType.SHOOTOUT_AUDIO,
    )
    child_result = await session.execute(child_stmt)
    audio_children = child_result.scalars().all()
    if not audio_children:
        return

    total_children = len(audio_children)
    completed_children = sum(1 for job in audio_children if job.status == JobStatus.COMPLETED)
    failed_class_children = sum(1 for job in audio_children if job.status in FAILED_CLASS)

    now = datetime.now(UTC)
    parent_job.progress = int((completed_children / total_children) * 100)
    parent_job.last_heartbeat = now

    if failed_class_children > 0:
        breakdown = ", ".join(
            f"{count} {status.value}"
            for status in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTERED)
            if (count := sum(1 for job in audio_children if job.status == status))
        )
        if parent_job.status.can_transition_to(JobStatus.FAILED):
            parent_job.status = JobStatus.FAILED
            parent_job.error = (
                f"{failed_class_children} chain job(s) terminal without success: {breakdown}"
            )
            parent_job.completed_at = now
        if shootout is not None and shootout.status != ShootoutStatus.COMPLETED:
            shootout.status = ShootoutStatus.FAILED
        return

    if parent_job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
        parent_job.status = JobStatus.RUNNING
        if parent_job.started_at is None:
            parent_job.started_at = now

    if shootout is not None and shootout.status not in {
        ShootoutStatus.COMPLETED,
        ShootoutStatus.FAILED,
    }:
        shootout.status = ShootoutStatus.PROCESSING

    if completed_children == total_children:
        master_stmt = select(Job).where(
            Job.parent_job_id == parent_job_id,
            Job.job_type == JobType.SHOOTOUT_MASTER,
        )
        master_result = await session.execute(master_stmt)
        master_job = master_result.scalar_one_or_none()
        if master_job is None:
            master_job = Job(
                user_id=parent_job.user_id,
                job_type=JobType.SHOOTOUT_MASTER,
                parent_job_id=parent_job.id,
                entity_id=parent_job.entity_id,
                status=JobStatus.PENDING,
                progress=0,
            )
            session.add(master_job)
            await session.flush()
            # Enqueue through the outbox in the same transaction: the master
            # job's creation, its QUEUED flip, and the pgmq send commit
            # together with the reconcile that decided them.
            await enqueue_job(session, master_job.id, message="Queued for master audio creation")
