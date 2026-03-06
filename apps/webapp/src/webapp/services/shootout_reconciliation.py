"""Shootout reconciliation logic shared between audio-worker and video-worker."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand
from messaging.db import get_session_no_tx as get_session
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus


async def _dispatch_master_job(master_job_id: UUID, database_url: str) -> None:
    """Dispatch a pending SHOOTOUT_MASTER job via pgmq audio_commands."""
    async with get_session(database_url) as session:
        stmt = select(Job).where(Job.id == master_job_id).with_for_update()
        result = await session.execute(stmt)
        master_job = result.scalar_one_or_none()
        if master_job is None or master_job.status != JobStatus.PENDING:
            return

        pgmq = PgmqClient(session)
        cmd = ProcessAudioCommand(
            source_bc="audio-worker",
            payload={
                "job_id": str(master_job.id),
                "shootout_id": str(master_job.entity_id),
                "user_id": str(master_job.user_id),
            },
        )
        await pgmq.send("audio_commands", cmd)
        master_job.status = JobStatus.QUEUED
        master_job.message = "Queued for master audio creation"
        await session.commit()


async def reconcile_parent_after_audio(parent_job_id: UUID, database_url: str) -> None:
    """Reconcile parent SHOOTOUT state from child SHOOTOUT_AUDIO results."""
    master_job_id: UUID | None = None

    async with get_session(database_url) as session:
        parent_stmt = select(Job).where(Job.id == parent_job_id).with_for_update()
        parent_result = await session.execute(parent_stmt)
        parent_job = parent_result.scalar_one_or_none()
        if parent_job is None or parent_job.entity_id is None:
            return

        shootout_stmt = select(Shootout).where(Shootout.id == parent_job.entity_id)
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
        failed_children = sum(1 for job in audio_children if job.status == JobStatus.FAILED)

        parent_job.progress = int((completed_children / total_children) * 100)
        parent_job.last_heartbeat = datetime.now(UTC)

        if failed_children > 0:
            parent_job.status = JobStatus.FAILED
            parent_job.error = f"{failed_children} chain job(s) failed"
            parent_job.completed_at = datetime.now(UTC)
            if shootout is not None:
                shootout.status = ShootoutStatus.FAILED
            await session.commit()
            return

        if parent_job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
            parent_job.status = JobStatus.RUNNING
            if parent_job.started_at is None:
                parent_job.started_at = datetime.now(UTC)

        if shootout is not None:
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
            master_job_id = master_job.id

        await session.commit()

    if master_job_id is not None:
        await _dispatch_master_job(master_job_id, database_url)
