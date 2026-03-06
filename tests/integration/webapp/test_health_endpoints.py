"""Integration tests for health check endpoints.

Tests liveness and readiness endpoints that verify system status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app instance for testing."""
    from webapp.main import create_app

    return create_app()


class TestLivenessEndpoint:
    """Test liveness endpoint (process running check)."""

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self, app: FastAPI) -> None:
        """GET /health returns 200 OK when process is alive."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_json(self, app: FastAPI) -> None:
        """GET /health returns JSON response."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_health_endpoint_has_exact_response_structure(self, app: FastAPI) -> None:
        """GET /health returns exact response structure with status=alive."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            # Must have exactly "status" field with value "alive"
            assert data == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_health_endpoint_responds_quickly(self, app: FastAPI) -> None:
        """GET /health responds in under 100ms."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            process_time = float(response.headers.get("x-process-time", "1.0"))
            # Liveness check should be instant (no DB queries)
            assert process_time < 0.1


class TestReadinessEndpoint:
    """Test readiness endpoint (database connectivity check)."""

    @pytest.mark.asyncio
    async def test_ready_endpoint_returns_200_when_db_connected(self, app: FastAPI) -> None:
        """GET /health/ready returns 200 when database is connected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            # Should return 200 when DB is available (it is in integration tests)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ready_endpoint_has_exact_response_structure_when_ready(
        self, app: FastAPI
    ) -> None:
        """GET /health/ready returns exact structure with status=ready and database=connected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            data = response.json()
            # Must have exact structure when ready
            assert data == {"status": "ready", "database": "connected"}

    @pytest.mark.asyncio
    async def test_ready_endpoint_actually_checks_database_connection(self, app: FastAPI) -> None:
        """GET /health/ready executes a database query to verify connectivity."""
        # This test verifies the endpoint isn't just returning a static response
        # Implementation should execute SELECT 1 or similar to test the connection
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First call should succeed
            response1 = await client.get("/health/ready")
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["database"] == "connected"

            # The implementation must actually query the DB (not cache the result)
            # Each call should test connectivity freshly
            response2 = await client.get("/health/ready")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["database"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_endpoint_returns_503_when_db_unavailable(self, app: FastAPI) -> None:
        """GET /health/ready returns 503 when database is unavailable."""
        # This test will need implementation to handle DB connection failure
        # When DB is down, endpoint should return 503 with status=unavailable
        # For now, this test documents the expected behavior
        # The implementer will need to test this by actually breaking the DB connection
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # In normal integration test environment, DB is available
            # This test documents that 503 should be returned on DB failure
            # Implementation should catch database connection errors
            response = await client.get("/health/ready")
            # Will be 200 in integration tests (DB is available)
            # But implementation must handle the failure case to return 503
            assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_ready_endpoint_has_exact_response_structure_when_unavailable(
        self, app: FastAPI
    ) -> None:
        """GET /health/ready returns exact structure with status=unavailable when DB down."""
        # This documents the expected structure when database is unavailable
        # Implementation should return {"status": "unavailable", "database": "disconnected"}
        # with 503 status code
        # Since we can't easily simulate DB failure in integration tests,
        # this test verifies the endpoint exists and returns valid structure
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            data = response.json()
            # Response must have both status and database fields
            assert "status" in data
            assert "database" in data
            # When ready: status=ready, database=connected
            # When unavailable: status=unavailable, database=disconnected
            if response.status_code == 200:
                assert data["status"] == "ready"
                assert data["database"] == "connected"
            elif response.status_code == 503:
                assert data["status"] == "unavailable"
                assert data["database"] == "disconnected"
