"""Video command consumer and shootout orchestration logic."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand, RenderVideoCommand
from messaging.consumer_base import BaseConsumer
from messaging.db import get_session_no_tx as get_session
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus

if TYPE_CHECKING:
    from messaging.envelope import MessageEnvelope


async def _dispatch_pending_audio_children(parent_job_id: UUID, database_url: str) -> None:
    """Dispatch pending SHOOTOUT_AUDIO children via pgmq audio_commands."""
    async with get_session(database_url) as session:
        parent_stmt = select(Job).where(Job.id == parent_job_id)
        parent_result = await session.execute(parent_stmt)
        parent_job = parent_result.scalar_one_or_none()
        if parent_job is None or parent_job.entity_id is None:
            return

        stmt = select(Job).where(
            Job.parent_job_id == parent_job_id,
            Job.job_type == JobType.SHOOTOUT_AUDIO,
            Job.status == JobStatus.PENDING,
        )
        result = await session.execute(stmt)
        pending_children = result.scalars().all()

        pgmq = PgmqClient(session)
        for child in pending_children:
            cmd = ProcessAudioCommand(
                payload={
                    "job_id": str(child.id),
                    "shootout_id": str(parent_job.entity_id),
                    "user_id": str(child.user_id),
                }
            )
            await pgmq.publish("audio_commands", cmd)
            child.status = JobStatus.QUEUED
            child.message = "Queued for chain processing"

        await session.commit()


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
            payload={
                "job_id": str(master_job.id),
                "shootout_id": str(master_job.entity_id),
                "user_id": str(master_job.user_id),
            }
        )
        await pgmq.publish("audio_commands", cmd)
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


async def process_shootout_job(job_id: UUID) -> None:
    """Handle SHOOTOUT by spawning and dispatching chain jobs."""
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")

    async with get_session(database_url) as session:
        parent_stmt = select(Job).where(Job.id == job_id).options(joinedload(Job.user))
        parent_result = await session.execute(parent_stmt)
        parent_job = parent_result.unique().scalar_one_or_none()
        if parent_job is None:
            raise ValueError(f"Job {job_id} not found")
        if parent_job.entity_id is None:
            raise ValueError(f"Job {job_id} has no entity_id set")

        shootout_stmt = (
            select(Shootout)
            .where(Shootout.id == parent_job.entity_id)
            .options(joinedload(Shootout.chains))
        )
        shootout_result = await session.execute(shootout_stmt)
        shootout = shootout_result.unique().scalar_one_or_none()
        if shootout is None:
            raise ValueError(f"Shootout {parent_job.entity_id} not found")
        if not shootout.chains:
            raise ValueError(f"Shootout {shootout.id} has no chains")

        parent_job.status = JobStatus.RUNNING
        if parent_job.started_at is None:
            parent_job.started_at = datetime.now(UTC)
        parent_job.last_heartbeat = datetime.now(UTC)
        parent_job.message = "Spawning chain jobs"

        shootout.status = ShootoutStatus.PROCESSING

        child_stmt = select(Job).where(
            Job.parent_job_id == parent_job.id,
            Job.job_type == JobType.SHOOTOUT_AUDIO,
        )
        child_result = await session.execute(child_stmt)
        existing_children = child_result.scalars().all()
        existing_by_chain_id = {child.entity_id: child for child in existing_children}

        for chain in shootout.chains:
            if chain.id in existing_by_chain_id:
                continue
            child_job = Job(
                user_id=parent_job.user_id,
                job_type=JobType.SHOOTOUT_AUDIO,
                parent_job_id=parent_job.id,
                entity_id=chain.id,
                status=JobStatus.PENDING,
                progress=0,
            )
            session.add(child_job)

        await session.commit()

    await _dispatch_pending_audio_children(job_id, database_url)
    await reconcile_parent_after_audio(job_id, database_url)


async def _update_parent_progress(parent_job_id: UUID, database_url: str) -> None:
    """Backwards-compatible alias for parent reconciliation."""
    await reconcile_parent_after_audio(parent_job_id, database_url)


class RenderVideoConsumer(BaseConsumer):
    """Consume render_video queue commands."""

    def __init__(self, session) -> None:
        super().__init__(
            message_bus=PgmqClient(session),
            queue_name="video_commands",
            dead_letter_queue="dead_letter",
        )
        self._session = session

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Handle one render_video command envelope."""
        command = RenderVideoCommand.model_validate(envelope.model_dump(mode="python"))
        job_id = UUID(command.payload["job_id"])
        await process_shootout_job(job_id)

    async def commit_message(self) -> None:
        """Commit queue archive in the session used by the pgmq client."""
        await self._session.commit()

    async def rollback_message(self) -> None:
        """Rollback failed message attempts before retry/DLQ decisions."""
        await self._session.rollback()

    async def reset_message_context(self) -> None:
        """Clear session identity state between long-lived message iterations."""
        self._session.expunge_all()
