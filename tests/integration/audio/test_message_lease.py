"""Message lease renewal: heartbeat + visibility extension while work runs."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text

from audio_worker.lease import MessageLease
from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _patch_lease_session(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import audio_worker.lease as lease_mod

    @asynccontextmanager
    async def _factory(_url: str) -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    monkeypatch.setattr(lease_mod, "get_session", _factory)


async def _running_job_with_message(db_session: AsyncSession) -> tuple[Job, int]:
    pgmq = PgmqClient(db_session)
    await pgmq.create_queue("audio_commands")
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SHOOTOUT_AUDIO,
        entity_id=uuid4(),
        status=JobStatus.RUNNING,
        progress=0,
    )
    db_session.add(job)
    await db_session.flush()
    msg_id = await pgmq.send(
        "audio_commands",
        {"message_type": "process_audio", "payload": {"job_id": str(job.id)}},
    )
    return job, msg_id


@pytest.mark.asyncio
@pytest.mark.integration
class TestMessageLease:
    async def test_beats_renew_heartbeat_and_visibility(self, db_session: AsyncSession) -> None:
        job, msg_id = await _running_job_with_message(db_session)
        await db_session.execute(
            text("UPDATE core_jobs SET last_heartbeat = now() - interval '1 hour' WHERE id = :id"),
            {"id": str(job.id)},
        )
        vt_before = (
            await db_session.execute(
                text("SELECT vt FROM pgmq.q_audio_commands WHERE msg_id = :m"),
                {"m": msg_id},
            )
        ).scalar_one()

        async with MessageLease(
            "unused-patched", "audio_commands", msg_id, job.id, interval_seconds=0.05
        ):
            await asyncio.sleep(0.2)

        await db_session.refresh(job)
        assert job.last_heartbeat is not None
        beat_age = (
            await db_session.execute(
                text(
                    "SELECT extract(epoch FROM now() - last_heartbeat) FROM core_jobs WHERE id = :id"
                ),
                {"id": str(job.id)},
            )
        ).scalar_one()
        assert beat_age < 60, "the lease task must have renewed last_heartbeat"

        vt_after = (
            await db_session.execute(
                text("SELECT vt FROM pgmq.q_audio_commands WHERE msg_id = :m"),
                {"m": msg_id},
            )
        ).scalar_one()
        assert vt_after > vt_before, "the lease task must extend the visibility timeout"

    async def test_terminal_job_stops_the_beats(self, db_session: AsyncSession) -> None:
        job, msg_id = await _running_job_with_message(db_session)
        job_id = job.id
        await db_session.execute(
            text("UPDATE core_jobs SET status = 'completed' WHERE id = :id"),
            {"id": str(job_id)},
        )
        db_session.expire(job)

        async with MessageLease(
            "unused-patched", "audio_commands", msg_id, job_id, interval_seconds=0.05
        ):
            await asyncio.sleep(0.2)

        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED
