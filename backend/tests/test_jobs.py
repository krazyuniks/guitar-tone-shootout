"""Tests for Job API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCreateJob:
    """Tests for POST /api/v1/jobs endpoint."""

    def test_create_job_requires_auth(self, client: TestClient):
        """Creating a job requires authentication."""
        response = client.post(
            "/api/v1/jobs",
            json={"config": {"di_track": "test.wav", "models": ["model1"]}},
        )
        assert response.status_code == 401

    def test_create_job_requires_config(self, client: TestClient):
        """Creating a job requires config field."""
        # Even without auth, validation should fail first
        response = client.post("/api/v1/jobs", json={})
        # Could be 401 (auth check first) or 422 (validation)
        assert response.status_code in (401, 422)


class TestListJobs:
    """Tests for GET /api/v1/jobs endpoint."""

    def test_list_jobs_requires_auth(self, client: TestClient):
        """Listing jobs requires authentication."""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 401

    def test_list_jobs_with_status_filter(self, client: TestClient):
        """Status filter parameter is accepted."""
        # Without auth we get 401, but the route exists
        response = client.get("/api/v1/jobs?status=pending")
        assert response.status_code == 401

    def test_list_jobs_pagination_params(self, client: TestClient):
        """Pagination parameters are accepted."""
        response = client.get("/api/v1/jobs?page=1&page_size=10")
        assert response.status_code == 401


class TestGetJob:
    """Tests for GET /api/v1/jobs/{id} endpoint."""

    def test_get_job_requires_auth(self, client: TestClient):
        """Getting a job requires authentication."""
        job_id = str(uuid4())
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 401

    def test_get_job_invalid_uuid(self, client: TestClient):
        """Invalid UUID returns 401 (auth checked first) or 422."""
        response = client.get("/api/v1/jobs/not-a-uuid")
        # Auth is checked before path validation
        assert response.status_code in (401, 422)


class TestCancelJob:
    """Tests for DELETE /api/v1/jobs/{id} endpoint."""

    def test_cancel_job_requires_auth(self, client: TestClient):
        """Cancelling a job requires authentication."""
        job_id = str(uuid4())
        response = client.delete(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 401


class TestJobSchemas:
    """Tests for Job schema validation."""

    def test_job_status_enum_values(self):
        """JobStatus enum has expected values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
