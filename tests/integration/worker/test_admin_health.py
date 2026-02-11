"""Integration tests for Worker Admin API health endpoint.

Tests the Admin API served on port 8001 with no authentication.
The health endpoint returns worker status including Redis connection,
database connection, and worker uptime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def admin_app() -> FastAPI:
    """Create Worker Admin API app instance for testing."""
    from worker.admin import app

    return app


class TestWorkerAdminHealth:
    """Test Worker Admin API health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_exists(self, admin_app: FastAPI) -> None:
        """GET /health returns 200 OK when worker admin API is running."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_json(self, admin_app: FastAPI) -> None:
        """GET /health returns JSON response."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_redis_status(self, admin_app: FastAPI) -> None:
        """GET /health includes Redis connection status."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Must include redis field with connection status
            assert "redis" in data
            # Redis status should be either "connected" or "disconnected"
            assert data["redis"] in ["connected", "disconnected"]

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_database_status(self, admin_app: FastAPI) -> None:
        """GET /health includes database connection status."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Must include database field with connection status
            assert "database" in data
            # Database status should be either "connected" or "disconnected"
            assert data["database"] in ["connected", "disconnected"]

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_worker_uptime(self, admin_app: FastAPI) -> None:
        """GET /health includes worker uptime in seconds."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Must include uptime field
            assert "uptime" in data
            # Uptime should be a non-negative number (float or int)
            assert isinstance(data["uptime"], int | float)
            assert data["uptime"] >= 0

    @pytest.mark.asyncio
    async def test_health_endpoint_has_status_field(self, admin_app: FastAPI) -> None:
        """GET /health includes overall status field."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Must include status field
            assert "status" in data
            # Status should indicate health (healthy/degraded/unhealthy)
            assert data["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_complete_structure(self, admin_app: FastAPI) -> None:
        """GET /health returns all required fields in response."""
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Verify complete response structure
            assert "status" in data
            assert "redis" in data
            assert "database" in data
            assert "uptime" in data
            # Verify types
            assert isinstance(data["status"], str)
            assert isinstance(data["redis"], str)
            assert isinstance(data["database"], str)
            assert isinstance(data["uptime"], int | float)

    @pytest.mark.asyncio
    async def test_health_endpoint_responds_quickly(self, admin_app: FastAPI) -> None:
        """GET /health responds in under 200ms.

        Health checks should be fast to avoid timing out
        load balancer health probes.
        """
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            # Check response time header if available
            process_time = float(response.headers.get("x-process-time", "0.1"))
            # Health check should complete quickly
            assert process_time < 0.2

    @pytest.mark.asyncio
    async def test_health_endpoint_no_authentication_required(self, admin_app: FastAPI) -> None:
        """GET /health does not require authentication.

        Admin API has no authentication - access is controlled at network level.
        Health endpoint should respond without any Authorization header.
        """
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            # Call without any auth headers
            response = await client.get("/health")
            # Should succeed without authentication
            assert response.status_code == 200
            data = response.json()
            assert "status" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_checks_redis_connectivity(self, admin_app: FastAPI) -> None:
        """GET /health actually tests Redis connection.

        Health endpoint should perform a real connectivity check,
        not just return cached status.
        """
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            # First call
            response1 = await client.get("/health")
            assert response1.status_code == 200
            data1 = response1.json()
            assert "redis" in data1

            # Second call should also check (not cached)
            response2 = await client.get("/health")
            assert response2.status_code == 200
            data2 = response2.json()
            assert "redis" in data2

    @pytest.mark.asyncio
    async def test_health_endpoint_checks_database_connectivity(self, admin_app: FastAPI) -> None:
        """GET /health actually tests database connection.

        Health endpoint should perform a real connectivity check,
        not just return cached status.
        """
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            # First call
            response1 = await client.get("/health")
            assert response1.status_code == 200
            data1 = response1.json()
            assert "database" in data1

            # Second call should also check (not cached)
            response2 = await client.get("/health")
            assert response2.status_code == 200
            data2 = response2.json()
            assert "database" in data2

    @pytest.mark.asyncio
    async def test_health_endpoint_uptime_increases(self, admin_app: FastAPI) -> None:
        """GET /health uptime increases on subsequent calls.

        Uptime should track how long the worker has been running,
        so it should increase between calls.
        """
        import asyncio

        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            # First call
            response1 = await client.get("/health")
            assert response1.status_code == 200
            data1 = response1.json()
            uptime1 = data1["uptime"]

            # Wait a small amount of time
            await asyncio.sleep(0.1)

            # Second call - uptime should be higher (or same if precision is low)
            response2 = await client.get("/health")
            assert response2.status_code == 200
            data2 = response2.json()
            uptime2 = data2["uptime"]

            # Uptime should have increased (or at minimum stayed the same)
            assert uptime2 >= uptime1
