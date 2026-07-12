"""Integration tests for shootout processing trigger endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from gts.domain.entities.shootout import Shootout, ShootoutChain
from gts.domain.value_objects.job_status import JobStatus, JobType
from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
)
from webapp.adapters.persistence.models.shootout import (
    ShootoutManifest,
    ShootoutStatus,
    ShootoutVisibility,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.di_track import DITrack


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with shootout router."""
    from fastapi import FastAPI

    from webapp.api.v1.shootouts import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
async def _shootout_queue(db_session: AsyncSession) -> None:
    """The outbox sends for real; ensure the target queue exists in this transaction."""
    from messaging.pgmq_client import PgmqClient

    await PgmqClient(db_session).create_queue("shootout_commands")


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for ownership tests."""
    user = User(username="otheruser", email="other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_signal_chain(db_session: AsyncSession, test_user: User) -> SignalChain:
    """Create a test signal chain."""
    chain = SignalChain(
        user_id=test_user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def draft_shootout_with_chains(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> ShootoutModel:
    """Create a draft shootout with at least one chain."""
    from webapp.adapters.persistence.repositories.shootout_repository import (
        SQLAlchemyShootoutRepository,
    )

    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain)

    # Override status to DRAFT (domain entity defaults to PENDING after processing)
    await repo.save(shootout)
    await db_session.flush()

    # Set status to DRAFT at DB level
    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout.id)
    result = await db_session.execute(stmt)
    db_shootout = result.scalar_one()
    db_shootout.status = ShootoutStatus.DRAFT
    await db_session.commit()
    await db_session.refresh(db_shootout)

    return db_shootout


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    from webapp.api.v1.shootouts import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def unauthenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    from webapp.api.v1.shootouts import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(None)  # No user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestProcessingTriggerEndpoint:
    """Test POST /api/shootouts/{shootout_id}/process endpoint."""

    async def test_returns_401_without_authentication(
        self,
        unauthenticated_client: AsyncClient,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint returns 401 when user is not authenticated."""
        response = await unauthenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    async def test_returns_404_for_nonexistent_shootout(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test endpoint returns 404 when shootout does not exist."""
        nonexistent_id = uuid4()

        response = await authenticated_client.post(f"/api/shootouts/{nonexistent_id}/process")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_returns_404_for_shootout_owned_by_different_user(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
        other_user: User,
    ) -> None:
        """Test endpoint returns 404 when shootout is owned by different user."""
        from webapp.api.v1.shootouts import set_session_override, set_user_override

        # Set up client authenticated as other_user
        set_session_override(db_session)
        set_user_override(other_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/shootouts/{draft_shootout_with_chains.id}/process")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Cleanup
        set_session_override(None)
        set_user_override(None)

    async def test_returns_400_for_shootout_with_no_chains(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_di_track: DITrack,
    ) -> None:
        """Test endpoint returns 400 when shootout has no chains."""
        # Create shootout with no chains
        empty_shootout = ShootoutModel(
            id=uuid4(),
            user_id=test_user.id,
            name="Empty Shootout",
            di_track_id=test_di_track.id,
            status=ShootoutStatus.DRAFT,
        )
        db_session.add(empty_shootout)
        await db_session.commit()

        response = await authenticated_client.post(f"/api/shootouts/{empty_shootout.id}/process")

        assert response.status_code == 400
        assert "no chains" in response.json()["detail"].lower()

    async def test_returns_400_for_non_draft_shootout(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint returns 400 when shootout is not in DRAFT status."""
        # Set shootout to PENDING status
        draft_shootout_with_chains.status = ShootoutStatus.PENDING
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    async def test_returns_400_for_processing_shootout(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint returns 400 when shootout is already PROCESSING."""
        draft_shootout_with_chains.status = ShootoutStatus.PROCESSING
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    async def test_returns_400_for_completed_shootout(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint returns 400 when shootout is already COMPLETED."""
        draft_shootout_with_chains.status = ShootoutStatus.COMPLETED
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    @pytest.mark.parametrize(
        "visibility",
        [ShootoutVisibility.PUBLIC, ShootoutVisibility.UNLISTED],
    )
    async def test_published_shootout_cannot_be_run_again(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
        visibility: ShootoutVisibility,
    ) -> None:
        """Public and unlisted manifests are immutable once published."""
        payload = {"chains": [{"media_path": "v1/segment.wav"}]}
        draft_shootout_with_chains.status = ShootoutStatus.COMPLETED
        draft_shootout_with_chains.visibility = visibility
        manifest = ShootoutManifest(
            shootout_id=draft_shootout_with_chains.id,
            version=draft_shootout_with_chains.render_version,
            payload=payload,
        )
        db_session.add(manifest)
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Published shootouts are immutable; create a new shootout for another run"
        }
        assert await db_session.scalar(select(JobModel.id)) is None
        await db_session.refresh(draft_shootout_with_chains)
        await db_session.refresh(manifest)
        assert draft_shootout_with_chains.render_version == 1
        assert manifest.payload == payload

    async def test_creates_job_record_queued(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
        test_user: User,
    ) -> None:
        """The endpoint creates the Job and the outbox flips it to QUEUED."""
        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        # Verify response
        assert response.status_code == 202

        # Verify Job was created and enqueued in the same transaction
        stmt = select(JobModel).where(JobModel.user_id == test_user.id)
        result = await db_session.execute(stmt)
        jobs = result.scalars().all()

        assert len(jobs) == 1
        job = jobs[0]
        assert job.job_type == JobType.SHOOTOUT.value
        assert job.entity_id == draft_shootout_with_chains.id
        assert job.user_id == test_user.id
        assert job.status == JobStatus.QUEUED.value

    async def test_updates_shootout_status_to_pending(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint updates shootout status to PENDING."""
        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 202

        # Verify shootout status updated
        await db_session.refresh(draft_shootout_with_chains)
        assert draft_shootout_with_chains.status == ShootoutStatus.PENDING

    async def test_returns_202_with_job_id(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """Test endpoint returns 202 with job_id in response body."""
        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 202

        # Verify response body
        body = response.json()
        assert "job_id" in body
        assert UUID(body["job_id"])  # Validates it's a valid UUID

    async def test_job_id_in_response_matches_created_job(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
        test_user: User,
    ) -> None:
        """Test job_id returned in response matches the Job created in DB."""
        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 202
        body = response.json()
        returned_job_id = UUID(body["job_id"])

        # Fetch job from DB
        stmt = select(JobModel).where(JobModel.id == returned_job_id)
        result = await db_session.execute(stmt)
        db_job = result.scalar_one_or_none()

        assert db_job is not None
        assert db_job.user_id == test_user.id
        assert db_job.entity_id == draft_shootout_with_chains.id

    async def test_sends_start_shootout_command_without_sweep(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        draft_shootout_with_chains: ShootoutModel,
    ) -> None:
        """The start_shootout message is on shootout_commands immediately.

        Processing starts without waiting on the fallback dispatch sweep:
        the pgmq send commits with the job-row write (transactional outbox).
        """
        response = await authenticated_client.post(
            f"/api/shootouts/{draft_shootout_with_chains.id}/process"
        )

        assert response.status_code == 202
        returned_job_id = response.json()["job_id"]

        result = await db_session.execute(text("SELECT message FROM pgmq.q_shootout_commands"))
        messages = [row[0] for row in result.fetchall()]
        assert len(messages) == 1
        assert messages[0]["message_type"] == "start_shootout"
        assert messages[0]["payload"]["job_id"] == returned_job_id
