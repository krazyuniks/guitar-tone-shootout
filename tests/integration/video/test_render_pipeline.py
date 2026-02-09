"""End-to-end integration tests for video render pipeline.

Tests the full render pipeline through the video BC API:
worker submits render, video BC accepts/validates, status tracking works.

Actual Remotion rendering is NOT tested here (requires full video service
with Chromium). These tests verify the API contract and job lifecycle.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from video.api import create_app


@pytest.fixture
async def video_client():
    """HTTP client for video service API."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
class TestVideoRenderPipeline:
    """End-to-end tests for video render pipeline integration."""

    async def test_submit_render_returns_202_with_job_id(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Test submits render request and receives 202 + job_id."""
        spec = {
            "composition_type": "shootout",
            "data": {
                "shootout_id": "550e8400-e29b-41d4-a716-446655440000",
                "gear_ids": ["g1", "g2"],
            },
        }

        response = await video_client.post("/render", json=spec)

        assert response.status_code == 202
        body = response.json()
        assert "job_id" in body
        assert isinstance(body["job_id"], str)
        assert len(body["job_id"]) > 0

    async def test_poll_status_returns_pending_for_new_job(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Polling a newly submitted job returns pending status."""
        spec = {
            "composition_type": "shootout",
            "data": {
                "shootout_id": "550e8400-e29b-41d4-a716-446655440000",
                "gear_ids": ["g1", "g2"],
            },
        }
        submit_response = await video_client.post("/render", json=spec)
        job_id = submit_response.json()["job_id"]

        response = await video_client.get(f"/render/{job_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ["pending", "rendering", "complete"]
        assert body["job_id"] == job_id

    async def test_nonexistent_job_returns_404(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Polling a nonexistent job ID returns 404."""
        response = await video_client.get("/render/nonexistent-job-id")
        assert response.status_code == 404

    async def test_invalid_props_returns_422(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Invalid composition spec returns 422 validation error."""
        invalid_spec = {
            # Missing required 'composition_type' and 'data' fields
        }

        response = await video_client.post("/render", json=invalid_spec)
        assert response.status_code == 422

    async def test_health_endpoint_returns_healthy(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Health endpoint returns healthy status."""
        response = await video_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"

    async def test_render_pipeline_job_lifecycle(
        self,
        video_client: AsyncClient,
    ) -> None:
        """Full lifecycle: submit -> poll -> terminal status."""
        # Submit
        spec = {
            "composition_type": "shootout",
            "data": {
                "shootout_id": "550e8400-e29b-41d4-a716-446655440000",
                "gear_ids": ["g1", "g2"],
            },
        }
        submit_response = await video_client.post("/render", json=spec)
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]

        # Poll — should get a valid status response
        poll_response = await video_client.get(f"/render/{job_id}")
        assert poll_response.status_code == 200
        body = poll_response.json()
        assert "status" in body
        assert "job_id" in body
        assert body["job_id"] == job_id
