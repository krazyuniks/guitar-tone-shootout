"""Transactional job enqueue - the single outbox seam between job rows and pgmq.

Per docs/design/job-system-contract.md, every enqueue is one transaction: the
pgmq send and the PENDING -> QUEUED status flip commit together with whatever
job-row writes the caller staged on the same session. There is no HTTP hop
between the webapp and the workers. Callers: the user process trigger, the
admin enqueue endpoint, the retry paths, and the scheduled dispatch sweep.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand, StartShootoutCommand
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from messaging.envelope import MessageEnvelope

_AUDIO_JOB_TYPES = frozenset(
    {JobType.SHOOTOUT_AUDIO, JobType.SHOOTOUT_MASTER, JobType.AUDIO_PROCESSING}
)


class JobDispatchError(Exception):
    """Base for enqueue failures the caller maps to a response."""


class JobNotFoundError(JobDispatchError):
    """The job row does not exist."""


class JobNotPendingError(JobDispatchError):
    """Only PENDING jobs may be enqueued (PENDING -> QUEUED is the sole edge)."""

    def __init__(self, status: JobStatus) -> None:
        self.status = status
        super().__init__(f"Cannot enqueue job in {status.value} state")


class UnroutableJobTypeError(JobDispatchError):
    """The job type has no queue route (e.g. self-managed SOURCE_SYNC)."""

    def __init__(self, job_type: JobType) -> None:
        self.job_type = job_type
        super().__init__(f"No queue route for job type: {job_type.value}")


def _route(job: Job, source_bc: str) -> tuple[str, MessageEnvelope]:
    """Map a job to its queue and command message."""
    if job.job_type == JobType.SHOOTOUT:
        return (
            "shootout_commands",
            StartShootoutCommand(source_bc=source_bc, payload={"job_id": str(job.id)}),
        )
    if job.job_type in _AUDIO_JOB_TYPES:
        return (
            "audio_commands",
            ProcessAudioCommand(
                source_bc=source_bc,
                payload={
                    "job_id": str(job.id),
                    "shootout_id": str(job.entity_id),
                    "user_id": str(job.user_id),
                },
            ),
        )
    raise UnroutableJobTypeError(job.job_type)


async def enqueue_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    source_bc: str = "webapp",
    message: str | None = None,
) -> Job:
    """Send the job's command to its queue and flip PENDING -> QUEUED, then commit.

    Locks the job row, so concurrent dispatchers (route vs fallback sweep)
    serialise: the loser sees QUEUED and raises JobNotPendingError instead of
    double-sending. Commits the session - the caller's staged writes (job-row
    insert, shootout status flip) land in the same transaction as the send.
    """
    stmt = select(Job).where(Job.id == job_id).with_for_update()
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    if job.status != JobStatus.PENDING:
        raise JobNotPendingError(job.status)

    queue, command = _route(job, source_bc)
    pgmq = PgmqClient(session)
    # The producer is self-sufficient: consumers create queues at startup, but
    # an enqueue must not depend on a consumer ever having run (idempotent).
    await pgmq.create_queue(queue)
    await pgmq.send(queue, command)
    job.status = JobStatus.QUEUED
    if message is not None:
        job.message = message
    await session.commit()
    return job
