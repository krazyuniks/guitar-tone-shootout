"""Shootout orchestration consumer: fan-out and reconciliation for shootout runs."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand, StartShootoutCommand
from messaging.consumer_base import BaseConsumer
from messaging.db import get_session_no_tx as get_session
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout
from webapp.services.job_transitions import (
    mark_job_dead_lettered,
)
from webapp.services.shootout_reconciliation import reconcile_parent_after_audio

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
        await pgmq.create_queue("audio_commands")
        for child in pending_children:
            cmd = ProcessAudioCommand(
                source_bc="shootout-orchestrator",
                payload={
                    "job_id": str(child.id),
                    "shootout_id": str(parent_job.entity_id),
                    "user_id": str(child.user_id),
                },
            )
            await pgmq.send("audio_commands", cmd)
            child.status = JobStatus.QUEUED
            child.message = "Queued for chain processing"

        await session.commit()


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

        # The consumer claimed the parent (RUNNING) before dispatching here;
        # the shootout's PROCESSING projection is reconcile_parent's, called
        # below - no direct status writes in the orchestrator.
        parent_job.message = "Spawning chain jobs"

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


class StartShootoutConsumer(BaseConsumer):
    """Consume start_shootout commands from the shootout orchestration queue."""

    def __init__(self, session) -> None:
        super().__init__(
            message_bus=PgmqClient(session),
            queue_name="shootout_commands",
            dead_letter_queue="dead_letter",
        )
        self._session = session

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Handle one shootout command envelope."""
        command = StartShootoutCommand.model_validate(envelope.model_dump(mode="python"))
        job_id = UUID(command.payload["job_id"])
        await process_shootout_job(job_id)

    async def on_dead_letter(self, message: dict[str, object], reason: str) -> None:
        """Couple the job row to the queue-level DLQ in the same commit."""
        await mark_job_dead_lettered(self._session, message, reason)

    async def commit_message(self) -> None:
        """Commit queue archive in the session used by the pgmq client."""
        await self._session.commit()

    async def rollback_message(self) -> None:
        """Rollback failed message attempts before retry/DLQ decisions."""
        await self._session.rollback()

    async def reset_message_context(self) -> None:
        """Clear session identity state between long-lived message iterations."""
        self._session.expunge_all()
