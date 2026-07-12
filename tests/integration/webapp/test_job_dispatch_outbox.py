"""Integration tests for the transactional enqueue outbox (webapp.services.job_dispatch).

Covers the routing table, the PENDING-only guard, and the regression the old
admin tests masked: enqueue must persist through a production-shaped
fresh-session-per-request path, not just a shared fixture session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.services.job_dispatch import (
    JobNotFoundError,
    JobNotPendingError,
    UnroutableJobTypeError,
    enqueue_job,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
async def _queues(db_session: AsyncSession, request: pytest.FixtureRequest) -> None:
    """The outbox sends for real; ensure both command queues exist."""
    if request.node.name == "test_admin_enqueue_persists_across_sessions":
        return
    pgmq = PgmqClient(db_session)
    await pgmq.create_queue("shootout_commands")
    await pgmq.create_queue("audio_commands")


async def _messages(db_session: AsyncSession, queue: str) -> list[dict]:
    result = await db_session.execute(text(f"SELECT message FROM pgmq.q_{queue}"))
    return [row[0] for row in result.fetchall()]


def _job(job_type: JobType, status: JobStatus = JobStatus.PENDING) -> Job:
    return Job(
        id=uuid4(),
        user_id=None,
        job_type=job_type,
        entity_id=uuid4(),
        status=status,
        progress=0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestEnqueueJobRouting:
    async def test_shootout_routes_to_shootout_commands(self, db_session: AsyncSession) -> None:
        job = _job(JobType.SHOOTOUT)
        db_session.add(job)
        await db_session.flush()

        await enqueue_job(db_session, job.id)

        assert job.status == JobStatus.QUEUED
        messages = await _messages(db_session, "shootout_commands")
        assert len(messages) == 1
        assert messages[0]["message_type"] == "start_shootout"
        assert messages[0]["payload"]["job_id"] == str(job.id)

    async def test_audio_types_route_to_audio_commands(self, db_session: AsyncSession) -> None:
        job = _job(JobType.SHOOTOUT_AUDIO)
        db_session.add(job)
        await db_session.flush()

        await enqueue_job(db_session, job.id)

        assert job.status == JobStatus.QUEUED
        messages = await _messages(db_session, "audio_commands")
        assert len(messages) == 1
        assert messages[0]["message_type"] == "process_audio"
        assert messages[0]["payload"]["job_id"] == str(job.id)
        assert messages[0]["payload"]["shootout_id"] == str(job.entity_id)

    async def test_finalise_routes_to_shootout_commands(self, db_session: AsyncSession) -> None:
        job = _job(JobType.SHOOTOUT_FINALISE)
        db_session.add(job)
        await db_session.flush()

        await enqueue_job(db_session, job.id)

        assert job.status == JobStatus.QUEUED
        messages = await _messages(db_session, "shootout_commands")
        assert len(messages) == 1
        assert messages[0]["message_type"] == "finalise_shootout"
        assert messages[0]["payload"]["job_id"] == str(job.id)

    async def test_non_pending_job_is_rejected_and_nothing_sent(
        self, db_session: AsyncSession
    ) -> None:
        """PENDING -> QUEUED is the only enqueue edge; a loser in the dispatch race no-ops."""
        job = _job(JobType.SHOOTOUT, status=JobStatus.QUEUED)
        db_session.add(job)
        await db_session.flush()

        with pytest.raises(JobNotPendingError):
            await enqueue_job(db_session, job.id)

        assert await _messages(db_session, "shootout_commands") == []

    async def test_source_sync_is_unroutable(self, db_session: AsyncSession) -> None:
        job = _job(JobType.SOURCE_SYNC)
        db_session.add(job)
        await db_session.flush()

        with pytest.raises(UnroutableJobTypeError):
            await enqueue_job(db_session, job.id)

        assert job.status == JobStatus.PENDING

    async def test_missing_job_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(JobNotFoundError):
            await enqueue_job(db_session, uuid4())


@pytest.mark.asyncio
@pytest.mark.integration
class TestAdminEnqueueGuard:
    async def test_non_pending_job_returns_409(self, db_session: AsyncSession) -> None:
        from fastapi import FastAPI

        from webapp.api.admin import _get_db, router

        job = _job(JobType.SHOOTOUT, status=JobStatus.RUNNING)
        db_session.add(job)
        await db_session.flush()

        app = FastAPI()
        app.include_router(router)

        async def override():
            yield db_session

        app.dependency_overrides[_get_db] = override
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/admin/enqueue", json={"job_id": str(job.id)})
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.integration
class TestFreshSessionPersistence:
    async def test_admin_enqueue_persists_across_sessions(self, core_engine: AsyncEngine) -> None:
        """Regression for the flush-and-discard admin surface.

        The old tests handed the endpoint the same SAVEPOINT session used for
        setup, so a missing commit was invisible. Here the request handler gets
        its own session from a factory, exactly as production get_db does; the
        enqueue must be visible from a third session afterwards.
        """
        from fastapi import FastAPI

        from webapp.api.admin import _get_db, router

        factory = async_sessionmaker(core_engine, class_=AsyncSession, expire_on_commit=False)
        job_id = uuid4()

        async with factory() as setup_session:
            await PgmqClient(setup_session).create_queue("shootout_commands")
            setup_session.add(
                Job(
                    id=job_id,
                    user_id=None,
                    job_type=JobType.SHOOTOUT,
                    entity_id=uuid4(),
                    status=JobStatus.PENDING,
                    progress=0,
                )
            )
            await setup_session.commit()

        app = FastAPI()
        app.include_router(router)

        async def fresh_session():
            async with factory() as session:
                yield session

        app.dependency_overrides[_get_db] = fresh_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/admin/enqueue", json={"job_id": str(job_id)})
            assert response.status_code == 202

            async with factory() as verify_session:
                job = (
                    await verify_session.execute(select(Job).where(Job.id == job_id))
                ).scalar_one()
                assert job.status == JobStatus.QUEUED
                result = await verify_session.execute(
                    text(
                        "SELECT message FROM pgmq.q_shootout_commands "
                        "WHERE message->'payload'->>'job_id' = :jid"
                    ),
                    {"jid": str(job_id)},
                )
                assert len(result.fetchall()) == 1
        finally:
            app.dependency_overrides.clear()
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text(
                        "DELETE FROM pgmq.q_shootout_commands "
                        "WHERE message->'payload'->>'job_id' = :jid"
                    ),
                    {"jid": str(job_id)},
                )
                await cleanup_session.execute(delete(Job).where(Job.id == job_id))
                await cleanup_session.commit()
