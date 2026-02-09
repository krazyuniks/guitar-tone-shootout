"""Integration tests for video service FastAPI endpoints."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.composition_spec import CompositionSpec
from video.api import create_app


@pytest.fixture
async def app():
    """Create FastAPI app instance."""
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for video service API."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.integration
class TestRenderEndpoint:
    """Tests for POST /render endpoint."""

    async def test_accepts_render_request(self, client: AsyncClient) -> None:
        """POST /render accepts composition spec and returns job_id."""
        response = await client.post(
            "/render",
            json={
                "composition_type": "shootout",
                "data": {"shootout_id": "s-123", "gear_ids": ["g1", "g2"]},
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert "job_id" in body
        assert isinstance(body["job_id"], str)
        assert len(body["job_id"]) > 0

    async def test_rejects_missing_composition_type(
        self, client: AsyncClient
    ) -> None:
        """POST /render returns 422 for missing composition_type."""
        response = await client.post(
            "/render",
            json={"data": {"test": "value"}},
        )

        assert response.status_code == 422

    async def test_rejects_missing_data(self, client: AsyncClient) -> None:
        """POST /render returns 422 for missing data field."""
        response = await client.post(
            "/render",
            json={"composition_type": "test"},
        )

        assert response.status_code == 422

    async def test_rejects_invalid_json(self, client: AsyncClient) -> None:
        """POST /render returns 422 for malformed JSON."""
        response = await client.post(
            "/render",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
class TestStatusEndpoint:
    """Tests for GET /render/{job_id} endpoint."""

    async def test_returns_job_status(self, client: AsyncClient) -> None:
        """GET /render/{job_id} returns render status."""
        # First submit a job
        submit_response = await client.post(
            "/render",
            json={
                "composition_type": "test",
                "data": {"test": "data"},
            },
        )
        job_id = submit_response.json()["job_id"]

        # Poll the status
        response = await client.get(f"/render/{job_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == job_id
        assert "status" in body
        assert body["status"] in ["pending", "rendering", "complete", "failed"]

    async def test_returns_404_for_unknown_job_id(
        self, client: AsyncClient
    ) -> None:
        """GET /render/{job_id} returns 404 for nonexistent job."""
        response = await client.get("/render/nonexistent-job-id")

        assert response.status_code == 404

    async def test_includes_output_path_when_complete(
        self, client: AsyncClient
    ) -> None:
        """GET /render/{job_id} includes output_path for completed jobs."""
        # This test verifies the schema shape - implementation will determine
        # when output_path is actually populated
        submit_response = await client.post(
            "/render",
            json={"composition_type": "test", "data": {}},
        )
        job_id = submit_response.json()["job_id"]

        response = await client.get(f"/render/{job_id}")
        body = response.json()

        # output_path should be null for pending jobs, str for complete
        assert "output_path" in body
        assert body["output_path"] is None or isinstance(
            body["output_path"], str
        )

    async def test_includes_error_message_when_failed(
        self, client: AsyncClient
    ) -> None:
        """GET /render/{job_id} includes error_message for failed jobs."""
        submit_response = await client.post(
            "/render",
            json={"composition_type": "test", "data": {}},
        )
        job_id = submit_response.json()["job_id"]

        response = await client.get(f"/render/{job_id}")
        body = response.json()

        # error_message should be null for non-failed jobs, str for failed
        assert "error_message" in body
        assert body["error_message"] is None or isinstance(
            body["error_message"], str
        )


@pytest.mark.asyncio
@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    async def test_returns_health_status(self, client: AsyncClient) -> None:
        """GET /health returns service health."""
        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert "status" in body
        assert body["status"] in ["healthy", "unhealthy"]

    async def test_health_check_does_not_require_auth(
        self, client: AsyncClient
    ) -> None:
        """GET /health is accessible without authentication."""
        # Health endpoint should be public
        response = await client.get("/health")

        assert response.status_code == 200
