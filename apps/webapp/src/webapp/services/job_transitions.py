"""Single-writer job transition service (docs/design/job-system-contract.md).

This module is the sole writer of Job.status and, via projection, of
Shootout.status; a structural guard test pins the shrinking allowlist of
not-yet-migrated legacy writers. Every move is validated against the
transition table (JobStatus.can_transition_to); a terminal move on a
SHOOTOUT_AUDIO child - and a retry claim back to PENDING - reconciles the
parent shootout in the same transaction.
Lock order, always: own job row -> parent job row -> shootout row.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.services.job_dispatch import is_queue_routable, send_and_mark_queued

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Terminal states that project the parent shootout to FAILED. CANCELLED maps
#: publicly to FAILED; the public lifecycle has five states, never more.
FAILED_CLASS = frozenset({JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTERED})

#: Delay before the retry sweep picks up an automatically retryable failure.
RETRY_BACKOFF = timedelta(seconds=120)

#: A RUNNING job whose heartbeat is younger than this holds a live lease.
LEASE_THRESHOLD = timedelta(seconds=120)

#: Job states a retry claim (-> PENDING) can come from.
_RETRY_SOURCES = frozenset({JobStatus.FAILED, JobStatus.DEAD_LETTERED})


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


class LiveLeaseError(TransitionError):
    """A RUNNING re-claim was attempted while another consumer's lease is live."""

    def __init__(self) -> None:
        super().__init__("Job holds a live lease; re-claim requires a stale heartbeat")


async def transition_job(
    session: AsyncSession,
    job_id: UUID,
    to_status: JobStatus,
    *,
    error: str | None = None,
    message: str | None = None,
    progress: int | None = None,
    result_path: str | None = None,
    renewal: bool = False,
    require_stale_lease: bool = False,
) -> Job:
    """Move a job to `to_status`, reconcile its parent if needed, and commit.

    Locks the job row, validates the move against the transition table (an
    invalid move raises before anything is written - a rejected no-op, never a
    half-write), applies bookkeeping, and for a SHOOTOUT_AUDIO child re-projects
    the parent shootout inside the same transaction on terminal moves and on
    retry claims. The service owns its commit; callers never commit around it.

    A RUNNING -> RUNNING move is either a lease heartbeat renewal by the
    holder (`renewal=True`) or a re-claim after redelivery, which requires the
    previous lease to be stale - a fresh heartbeat raises LiveLeaseError so a
    duplicate consumer can never steal live work.
    """
    stmt = select(Job).where(Job.id == job_id).with_for_update()
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundForTransitionError(f"Job {job_id} not found")
    if not job.status.can_transition_to(to_status):
        raise InvalidTransitionError(job.status, to_status)

    now = datetime.now(UTC)
    if (
        to_status == JobStatus.RUNNING
        and job.status == JobStatus.RUNNING
        and not renewal
        and job.last_heartbeat is not None
        and job.last_heartbeat > now - LEASE_THRESHOLD
    ):
        raise LiveLeaseError()

    # Reaper precondition, re-checked under the row lock: a lease renewal
    # committed between the reaper's SELECT and this transaction must win -
    # the reaper never fails a now-live job.
    if (
        require_stale_lease
        and job.status == JobStatus.RUNNING
        and job.last_heartbeat is not None
        and job.last_heartbeat > now - LEASE_THRESHOLD
    ):
        raise LiveLeaseError()

    from_status = job.status
    job.status = to_status
    if message is not None:
        job.message = message
    if error is not None:
        job.error = error
    if progress is not None:
        job.progress = progress
    if result_path is not None:
        job.result_path = result_path
    if to_status == JobStatus.RUNNING:
        if job.started_at is None:
            job.started_at = now
        job.last_heartbeat = now
    if to_status.is_terminal():
        job.completed_at = now

    # Retry bookkeeping (ADR-0005: bounded to max_attempts total, one automatic
    # retry). A failure under the cap schedules the sweep pickup; at the cap it
    # stays FAILED for admin action. Only queue-routable types auto-retry:
    # self-managed types (SOURCE_SYNC) have their own scheduler and no route
    # for the sweep to re-enqueue. A retry claim consumes an attempt and
    # clears the failure state.
    if to_status == JobStatus.FAILED:
        job.next_retry_at = (
            now + RETRY_BACKOFF
            if job.attempt < job.max_attempts and is_queue_routable(job.job_type)
            else None
        )
    if to_status == JobStatus.PENDING and from_status in _RETRY_SOURCES:
        job.attempt += 1
        job.error = None
        job.next_retry_at = None
        job.progress = 0
        job.completed_at = None
        job.result_path = None

    if (
        job.job_type == JobType.SHOOTOUT_AUDIO
        and job.parent_job_id is not None
        and (
            to_status.is_terminal()
            or (to_status == JobStatus.PENDING and from_status in _RETRY_SOURCES)
        )
    ):
        await reconcile_parent(session, job.parent_job_id)

    # Parent cancel blocks completion only (ADR-0005): a terminal move on the
    # parent SHOOTOUT job itself projects the shootout to FAILED unless it is
    # already published; in-flight children finish but are never published.
    if (
        to_status.is_terminal()
        and to_status != JobStatus.COMPLETED
        and job.job_type == JobType.SHOOTOUT
        and job.entity_id is not None
    ):
        shootout_stmt = select(Shootout).where(Shootout.id == job.entity_id).with_for_update()
        shootout_result = await session.execute(shootout_stmt)
        shootout = shootout_result.scalar_one_or_none()
        if shootout is not None and shootout.status != ShootoutStatus.COMPLETED:
            shootout.status = ShootoutStatus.FAILED

    await session.commit()
    return job


async def job_lease_is_live(session: AsyncSession, job_id: UUID) -> bool:
    """Whether the job is RUNNING under a fresh lease (heartbeat within threshold).

    Used by consumers to veto queue-level dead-lettering of healthy work whose
    redeliveries were skipped (SkipMessage does not consume attempts, but pgmq
    still counts reads).
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or job.status != JobStatus.RUNNING or job.last_heartbeat is None:
        return False
    return job.last_heartbeat > datetime.now(UTC) - LEASE_THRESHOLD


class ClaimOutcome:
    """Consumer claim results (docs/design/job-system-contract.md, Consumer contract)."""

    CLAIMED = "claimed"
    ALREADY_TERMINAL = "already_terminal"
    LIVE_LEASE = "live_lease"


async def claim_job(session: AsyncSession, job_id: UUID, *, message: str | None = None) -> str:
    """Run the consumer claim algorithm and return the outcome.

    CLAIMED: QUEUED -> RUNNING (or a stale RUNNING re-claim, or the
    self-managed PENDING -> RUNNING edge). ALREADY_TERMINAL: redelivered
    message for finished work - the caller archives it as a no-op.
    LIVE_LEASE: another consumer's lease is fresh - the caller must release
    the message without acknowledging it.
    """
    try:
        await transition_job(session, job_id, JobStatus.RUNNING, message=message)
    except LiveLeaseError:
        return ClaimOutcome.LIVE_LEASE
    except InvalidTransitionError as exc:
        if exc.current.is_terminal():
            return ClaimOutcome.ALREADY_TERMINAL
        raise
    return ClaimOutcome.CLAIMED


async def mark_job_dead_lettered(
    session: AsyncSession,
    message: dict[str, object],
    reason: str,
) -> None:
    """Couple a dead-lettered queue message to its job row, same transaction.

    Parses the job id from the message payload and transitions the job to
    DEAD_LETTERED in the caller's session, so the queue-level DLQ write and
    the job-row state commit together and can never diverge. Messages without
    a resolvable job row, and jobs already terminal, are logged and skipped -
    the DLQ envelope remains the redrive source either way.
    """
    payload = message.get("payload") if isinstance(message, dict) else None
    raw_job_id = payload.get("job_id") if isinstance(payload, dict) else None
    if raw_job_id is None:
        return
    try:
        job_id = UUID(str(raw_job_id))
    except ValueError:
        logger.warning("Dead-lettered message carries unparseable job_id %r", raw_job_id)
        return
    try:
        await transition_job(
            session, job_id, JobStatus.DEAD_LETTERED, error=f"dead-lettered: {reason}"
        )
    except TransitionError as exc:
        logger.warning("Dead-letter job coupling skipped for %s: %s", job_id, exc)


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

    # Retry re-projection: a FAILED, unpublished run whose failed-class
    # children have all been reclaimed comes back to life. Terminal per
    # generation: a published (COMPLETED) shootout never re-enters.
    if parent_job.status == JobStatus.FAILED:
        parent_job.status = JobStatus.RUNNING
        parent_job.error = None
        parent_job.completed_at = None

    if parent_job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
        parent_job.status = JobStatus.RUNNING
        if parent_job.started_at is None:
            parent_job.started_at = now

    # A terminal parent (cancelled/dead-lettered) blocks completion: children
    # finish but nothing is published and no master is spawned.
    if parent_job.status.is_terminal():
        return

    # No failed-class child exists here, so a FAILED projection is stale by
    # construction (a reclaimed prior failure) - revive it alongside the parent.
    if shootout is not None and shootout.status != ShootoutStatus.COMPLETED:
        shootout.status = ShootoutStatus.PROCESSING

    if completed_children == total_children:
        master_stmt = (
            select(Job)
            .where(
                Job.parent_job_id == parent_job_id,
                Job.job_type == JobType.SHOOTOUT_MASTER,
            )
            .with_for_update()
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
        if master_job.status == JobStatus.PENDING:
            # Outbox core, no commit: the master job's creation/recovery, its
            # QUEUED flip, and the pgmq send stay in the reconcile transaction,
            # committed by the transition service or the session wrapper.
            await send_and_mark_queued(
                session, master_job, message="Queued for master audio creation"
            )
