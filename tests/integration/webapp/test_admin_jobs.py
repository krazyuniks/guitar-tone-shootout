"""Integration tests for webapp Admin API job management endpoints.

Tests the Admin API job management endpoints at /api/admin with no authentication.
These endpoints allow listing jobs, viewing details with children, cancelling, and retrying jobs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4, uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def admin_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """Webapp Admin router mounted on a test FastAPI app with session override."""
    from fastapi import FastAPI

    from webapp.api.admin import _get_db as _admin_get_db
    from webapp.api.admin import router

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[_admin_get_db] = override_session
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
async def sample_job(db_session: AsyncSession) -> Job:
    """Create a sample job for testing."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
        progress=0,
        message="Test job",
        attempt=1,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def running_job(db_session: AsyncSession) -> Job:
    """Create a running job for testing."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.VIDEO_COMPOSE,
        status=JobStatus.RUNNING,
        progress=50,
        message="Processing video",
        started_at=datetime.now(UTC),
        attempt=1,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def failed_job(db_session: AsyncSession) -> Job:
    """Create a failed job for testing."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.FAILED,
        progress=0,
        message="Job failed",
        error="Something went wrong",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        attempt=2,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def completed_job(db_session: AsyncSession) -> Job:
    """Create a completed job for testing."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.MODEL_DOWNLOAD,
        status=JobStatus.COMPLETED,
        progress=100,
        message="Download complete",
        result_path="/tmp/model.nam",
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        completed_at=datetime.now(UTC),
        attempt=1,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def dead_lettered_job(db_session: AsyncSession) -> Job:
    """Create a dead-lettered job for testing."""
    job = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.NOTIFICATION,
        status=JobStatus.DEAD_LETTERED,
        progress=0,
        message="Job exceeded max attempts",
        error="Failed after 3 attempts",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        completed_at=datetime.now(UTC) - timedelta(minutes=30),
        attempt=3,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def dead_letter_message(
    db_session: AsyncSession, dead_lettered_job: Job
) -> dict[str, object]:
    """Put the dead-lettered job's original command in the queue-level DLQ."""
    original_message = {
        "message_id": str(uuid7()),
        "message_type": "process_audio",
        "source_bc": "shootout-orchestrator",
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": None,
        "payload": {"job_id": str(dead_lettered_job.id)},
    }
    dlq_message = {
        "failed_queue": "audio_commands",
        "failed_msg_id": 41,
        "failed_read_count": 4,
        "failed_at": datetime.now(UTC).isoformat(),
        "reason": "processing failed: broken input",
        "message": original_message,
    }
    await db_session.execute(text("SELECT pgmq.create('dead_letter')"))
    await db_session.execute(
        text("SELECT pgmq.send('dead_letter', CAST(:message AS jsonb))"),
        {"message": json.dumps(dlq_message)},
    )
    await db_session.commit()
    return dlq_message


@pytest.fixture
async def job_with_children(db_session: AsyncSession) -> tuple[Job, list[Job]]:
    """Create a parent job with child jobs for testing."""
    parent = Job(
        id=uuid4(),
        user_id=None,
        job_type=JobType.SHOOTOUT,
        status=JobStatus.RUNNING,
        progress=25,
        message="Processing shootout",
        started_at=datetime.now(UTC),
        attempt=1,
        max_attempts=3,
    )
    db_session.add(parent)
    await db_session.flush()

    children = []
    for i in range(3):
        child = Job(
            id=uuid4(),
            user_id=None,
            parent_job_id=parent.id,
            job_type=JobType.SHOOTOUT_AUDIO,
            status=JobStatus.COMPLETED if i == 0 else JobStatus.RUNNING,
            progress=100 if i == 0 else 50,
            message=f"Processing chain {i + 1}",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if i == 0 else None,
            attempt=1,
            max_attempts=3,
        )
        db_session.add(child)
        children.append(child)

    await db_session.commit()
    await db_session.refresh(parent)
    for child in children:
        await db_session.refresh(child)

    return parent, children


class TestJobsListEndpoint:
    """Test GET /api/admin/jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_endpoint_exists(self, admin_app: FastAPI, sample_job: Job) -> None:
        """GET /api/admin/jobs returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_jobs_returns_json(self, admin_app: FastAPI, sample_job: Job) -> None:
        """GET /api/admin/jobs returns JSON response."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_list_jobs_returns_all_jobs(
        self,
        admin_app: FastAPI,
        sample_job: Job,
        running_job: Job,
        completed_job: Job,
    ) -> None:
        """GET /api/admin/jobs returns all jobs when no filters applied."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)
            assert len(data) >= 3

            for job_data in data:
                assert "id" in job_data
                assert "job_type" in job_data
                assert "status" in job_data
                assert "progress" in job_data
                assert "created_at" in job_data

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(
        self,
        admin_app: FastAPI,
        sample_job: Job,
        running_job: Job,
        completed_job: Job,
    ) -> None:
        """GET /api/admin/jobs?status=running filters jobs by status."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs?status=running")
            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)
            assert len(data) >= 1
            for job_data in data:
                assert job_data["status"] == "running"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_job_type(
        self,
        admin_app: FastAPI,
        sample_job: Job,
        running_job: Job,
        completed_job: Job,
    ) -> None:
        """GET /api/admin/jobs?job_type=audio_processing filters jobs by type."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs?job_type=audio_processing")
            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)
            assert len(data) >= 1
            for job_data in data:
                assert job_data["job_type"] == "audio_processing"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_and_type(
        self,
        admin_app: FastAPI,
        sample_job: Job,
        running_job: Job,
        completed_job: Job,
        failed_job: Job,
    ) -> None:
        """GET /api/admin/jobs?status=failed&job_type=audio_processing filters by both."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs?status=failed&job_type=audio_processing")
            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)
            for job_data in data:
                assert job_data["status"] == "failed"
                assert job_data["job_type"] == "audio_processing"

    @pytest.mark.asyncio
    async def test_list_jobs_no_authentication_required(
        self, admin_app: FastAPI, sample_job: Job
    ) -> None:
        """GET /api/admin/jobs does not require authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200


class TestJobDetailEndpoint:
    """Test GET /api/admin/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_job_detail_endpoint_exists(self, admin_app: FastAPI, sample_job: Job) -> None:
        """GET /api/admin/jobs/{job_id} returns 200 OK for existing job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/admin/jobs/{sample_job.id}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_job_detail_returns_job_data(self, admin_app: FastAPI, sample_job: Job) -> None:
        """GET /api/admin/jobs/{job_id} returns complete job data."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/admin/jobs/{sample_job.id}")
            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(sample_job.id)
            assert data["job_type"] == sample_job.job_type.value
            assert data["status"] == sample_job.status.value
            assert data["progress"] == sample_job.progress
            assert data["message"] == sample_job.message
            assert data["attempt"] == sample_job.attempt
            assert data["max_attempts"] == sample_job.max_attempts

    @pytest.mark.asyncio
    async def test_job_detail_includes_child_jobs(
        self, admin_app: FastAPI, job_with_children: tuple[Job, list[Job]]
    ) -> None:
        """GET /api/admin/jobs/{job_id} includes child jobs for parent job."""
        parent, _children = job_with_children

        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/admin/jobs/{parent.id}")
            assert response.status_code == 200
            data = response.json()

            assert "children" in data
            assert isinstance(data["children"], list)
            assert len(data["children"]) == 3

            for child_data in data["children"]:
                assert "id" in child_data
                assert "job_type" in child_data
                assert "status" in child_data
                assert "progress" in child_data
                assert child_data["parent_job_id"] == str(parent.id)

    @pytest.mark.asyncio
    async def test_job_detail_returns_404_for_nonexistent_job(self, admin_app: FastAPI) -> None:
        """GET /api/admin/jobs/{job_id} returns 404 for nonexistent job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/admin/jobs/{uuid4()}")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_job_detail_no_authentication_required(
        self, admin_app: FastAPI, sample_job: Job
    ) -> None:
        """GET /api/admin/jobs/{job_id} does not require authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/admin/jobs/{sample_job.id}")
            assert response.status_code == 200


class TestJobCancelEndpoint:
    """Test POST /api/admin/jobs/{job_id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_job_endpoint_exists(self, admin_app: FastAPI, running_job: Job) -> None:
        """POST /api/admin/jobs/{job_id}/cancel returns 200 for running job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{running_job.id}/cancel")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cancel_job_changes_status(
        self, admin_app: FastAPI, running_job: Job, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/jobs/{job_id}/cancel sets job status to cancelled."""
        job_id = running_job.id
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/cancel")
            assert response.status_code == 200

            db_session.expire_all()
            result = await db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()
            assert job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_pending_job(
        self, admin_app: FastAPI, sample_job: Job, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/jobs/{job_id}/cancel works for pending job."""
        job_id = sample_job.id
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/cancel")
            assert response.status_code == 200

            db_session.expire_all()
            result = await db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()
            assert job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_already_completed_job_returns_409(
        self, admin_app: FastAPI, completed_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/cancel returns 409 for completed job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{completed_job.id}/cancel")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_already_failed_job_returns_409(
        self, admin_app: FastAPI, failed_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/cancel returns 409 for failed job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{failed_job.id}/cancel")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job_returns_404(self, admin_app: FastAPI) -> None:
        """POST /api/admin/jobs/{job_id}/cancel returns 404 for nonexistent job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{uuid4()}/cancel")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_job_no_authentication_required(
        self, admin_app: FastAPI, running_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/cancel does not require authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{running_job.id}/cancel")
            assert response.status_code == 200


class TestJobRetryEndpoint:
    """Test POST /api/admin/jobs/{job_id}/retry endpoint."""

    @pytest.mark.asyncio
    async def test_retry_job_endpoint_exists(self, admin_app: FastAPI, failed_job: Job) -> None:
        """POST /api/admin/jobs/{job_id}/retry returns 200 for failed job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{failed_job.id}/retry")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_retry_job_requeues_routable_job(
        self, admin_app: FastAPI, failed_job: Job, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry sends a routable job back to its queue."""
        job_id = failed_job.id
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/retry")
            assert response.status_code == 200

            db_session.expire_all()
            result = await db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()
            assert job.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_retry_job_clears_error(
        self, admin_app: FastAPI, failed_job: Job, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry clears error message."""
        job_id = failed_job.id
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/retry")
            assert response.status_code == 200

            db_session.expire_all()
            result = await db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()
            assert job.error is None

    @pytest.mark.asyncio
    async def test_retry_dead_lettered_job(
        self, admin_app: FastAPI, dead_lettered_job: Job, db_session: AsyncSession
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry works for dead-lettered job."""
        job_id = dead_lettered_job.id
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/retry")
            assert response.status_code == 200

            db_session.expire_all()
            result = await db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()
            assert job.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_retry_running_job_returns_409(
        self, admin_app: FastAPI, running_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry returns 409 for running job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{running_job.id}/retry")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_retry_completed_job_returns_409(
        self, admin_app: FastAPI, completed_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry returns 409 for completed job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{completed_job.id}/retry")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_retry_nonexistent_job_returns_404(self, admin_app: FastAPI) -> None:
        """POST /api/admin/jobs/{job_id}/retry returns 404 for nonexistent job."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{uuid4()}/retry")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_job_no_authentication_required(
        self, admin_app: FastAPI, failed_job: Job
    ) -> None:
        """POST /api/admin/jobs/{job_id}/retry does not require authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{failed_job.id}/retry")
            assert response.status_code == 200


class TestDeadLetterQueueLifecycle:
    """Test queue-level visibility and redrive on the admin API."""

    @pytest.mark.asyncio
    async def test_dead_letter_depth_comes_from_queue(
        self,
        admin_app: FastAPI,
        dead_letter_message: dict[str, object],
    ) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/queues/dead-letter/depth")

        assert response.status_code == 200
        assert response.json()["depth"] >= 1

    @pytest.mark.asyncio
    async def test_redrive_restores_original_envelope_and_queues_job(
        self,
        admin_app: FastAPI,
        dead_lettered_job: Job,
        dead_letter_message: dict[str, object],
        db_session: AsyncSession,
    ) -> None:
        job_id = dead_lettered_job.id
        await db_session.execute(text("SELECT pgmq.create('audio_commands')"))
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{job_id}/redrive")

        assert response.status_code == 200
        assert response.json()["status"] == "queued"

        db_session.expire_all()
        job_result = await db_session.execute(select(Job).where(Job.id == job_id))
        assert job_result.scalar_one().status == JobStatus.QUEUED

        source_result = await db_session.execute(
            text(
                "SELECT message FROM pgmq.q_audio_commands "
                "WHERE message->'payload'->>'job_id' = :job_id"
            ),
            {"job_id": str(job_id)},
        )
        assert source_result.scalar_one() == dead_letter_message["message"]

        dlq_result = await db_session.execute(
            text(
                "SELECT count(*) FROM pgmq.q_dead_letter "
                "WHERE message->'message'->'payload'->>'job_id' = :job_id"
            ),
            {"job_id": str(job_id)},
        )
        assert dlq_result.scalar_one() == 0

    @pytest.mark.asyncio
    async def test_redrive_requires_matching_dlq_envelope(
        self,
        admin_app: FastAPI,
        dead_lettered_job: Job,
    ) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/admin/jobs/{dead_lettered_job.id}/redrive")

        assert response.status_code == 404
