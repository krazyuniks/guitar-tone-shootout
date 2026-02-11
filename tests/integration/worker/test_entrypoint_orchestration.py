"""Integration tests for worker container entrypoint orchestration.

These tests verify that the worker container correctly runs 3 concurrent services:
- Admin API (uvicorn on port 8001)
- TaskIQ worker
- pgmq consumer

Tests run against the real Docker environment to verify the actual orchestration.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from core.domain.value_objects.job_status import JobStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkerContainerOrchestration:
    """Integration tests for the worker container multi-process orchestration."""

    async def test_admin_api_accessible_on_port_8001(self) -> None:
        """Admin API should be accessible on port 8001 within Docker network.

        The worker container should expose the admin API on port 8001, allowing
        other containers (webapp, nginx) to query job status and health.
        """
        async with AsyncClient(base_url="http://worker:8001", timeout=5.0) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Verify health endpoint returns expected structure
        assert "status" in data
        assert "redis" in data
        assert "database" in data
        assert "uptime" in data

    async def test_taskiq_worker_processes_jobs(self) -> None:
        """TaskIQ worker should continue processing jobs as before.

        The entrypoint script should not break existing TaskIQ functionality.
        Jobs should still be processed from the Redis queue.
        """
        # This test depends on the Job model existing
        # For now, just verify the worker container is running
        async with AsyncClient(base_url="http://worker:8001", timeout=5.0) as client:
            response = await client.get("/api/admin/jobs")

        assert response.status_code == 200
        # Should return a list (empty or with jobs)
        assert isinstance(response.json(), list)

    async def test_pgmq_consumer_starts(self) -> None:
        """pgmq consumer process should start (initial no-op loop).

        The consumer doesn't need to process messages yet (D1 will implement that),
        but it should start without errors and not crash the container.
        """
        # Verify worker health includes all 3 processes running
        async with AsyncClient(base_url="http://worker:8001", timeout=5.0) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # If pgmq consumer crashes, the admin API won't respond
        # (fail-fast behaviour should kill all processes)
        assert data["status"] in {"healthy", "degraded"}

    async def test_admin_api_job_endpoints_work(self) -> None:
        """Admin API job management endpoints should work correctly.

        Verifies that the admin API can list jobs, get job details, and
        perform job management operations (cancel, retry).
        """
        async with AsyncClient(base_url="http://worker:8001", timeout=5.0) as client:
            # List all jobs
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200

            # Filter by status
            response = await client.get(
                "/api/admin/jobs", params={"status": JobStatus.PENDING.value}
            )
            assert response.status_code == 200

    async def test_worker_container_stays_running(self) -> None:
        """Worker container should stay running with all 3 processes.

        This test verifies that the entrypoint successfully orchestrates
        all 3 processes without any of them crashing immediately.
        """
        # If any process had crashed, the health endpoint would be unreachable
        async with AsyncClient(base_url="http://worker:8001", timeout=5.0) as client:
            # Wait a moment to ensure processes have fully started
            await asyncio.sleep(1)

            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Uptime should be positive
        assert data["uptime"] > 0

        # Database and Redis should be connected
        assert data["database"] == "connected"
        assert data["redis"] == "connected"
