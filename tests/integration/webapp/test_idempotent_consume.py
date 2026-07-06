"""Idempotent consumption: the claim algorithm and the segment upsert.

The pre-fix shape: pgmq redelivered after the 60s visibility timeout, the
handler re-set RUNNING over terminal states and inserted duplicate
AudioSegment rows. The claim algorithm and the (shootout_chain_id, version)
upsert make every redelivery a no-op or a clean overwrite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.services.job_transitions import ClaimOutcome, claim_job

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import Platform


def _job(status: JobStatus) -> Job:
    return Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SHOOTOUT_AUDIO,
        entity_id=uuid4(),
        status=status,
        progress=0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestClaimAlgorithm:
    async def test_queued_job_is_claimed(self, db_session: AsyncSession) -> None:
        job = _job(JobStatus.QUEUED)
        db_session.add(job)
        await db_session.flush()

        outcome = await claim_job(db_session, job.id, message="Processing")

        assert outcome == ClaimOutcome.CLAIMED
        await db_session.refresh(job)
        assert job.status == JobStatus.RUNNING
        assert job.last_heartbeat is not None

    async def test_terminal_job_returns_already_terminal(self, db_session: AsyncSession) -> None:
        """Redelivered message for finished work: the caller archives, state untouched."""
        job = _job(JobStatus.COMPLETED)
        db_session.add(job)
        await db_session.flush()

        outcome = await claim_job(db_session, job.id)

        assert outcome == ClaimOutcome.ALREADY_TERMINAL
        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED

    async def test_fresh_lease_returns_live_lease(self, db_session: AsyncSession) -> None:
        job = _job(JobStatus.QUEUED)
        db_session.add(job)
        await db_session.flush()
        await claim_job(db_session, job.id)

        outcome = await claim_job(db_session, job.id)

        assert outcome == ClaimOutcome.LIVE_LEASE

    async def test_stale_lease_is_reclaimed(self, db_session: AsyncSession) -> None:
        job = _job(JobStatus.QUEUED)
        db_session.add(job)
        await db_session.flush()
        await claim_job(db_session, job.id)
        await db_session.execute(
            text(
                "UPDATE core_jobs SET last_heartbeat = now() - interval '10 minutes' WHERE id = :id"
            ),
            {"id": str(job.id)},
        )

        outcome = await claim_job(db_session, job.id)

        assert outcome == ClaimOutcome.CLAIMED


@pytest.mark.asyncio
@pytest.mark.integration
class TestSegmentUpsert:
    async def test_reprocessing_overwrites_instead_of_duplicating(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        shootout = Shootout(id=uuid4(), user_id=test_user.id, name="Upsert Shootout")
        db_session.add(shootout)
        signal_chain = SignalChain(user_id=test_user.id, name="SC", platform=Platform.NAM)
        db_session.add(signal_chain)
        await db_session.flush()
        chain = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=signal_chain.id,
            position=0,
            label="A",
        )
        db_session.add(chain)
        await db_session.flush()

        def _upsert(path: str):
            return (
                pg_insert(AudioSegment)
                .values(
                    shootout_chain_id=chain.id,
                    file_path=path,
                    duration_seconds=1.0,
                    integrated_lufs=-14.0,
                    peak_dbfs=-1.0,
                    version=1,
                )
                .on_conflict_do_update(
                    constraint="uq_audio_segments_chain_version",
                    set_={"file_path": path},
                )
            )

        await db_session.execute(_upsert("/v1/first.wav"))
        await db_session.execute(_upsert("/v1/second.wav"))

        segments = (
            (
                await db_session.execute(
                    select(AudioSegment).where(AudioSegment.shootout_chain_id == chain.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(segments) == 1
        assert segments[0].file_path == "/v1/second.wav"
