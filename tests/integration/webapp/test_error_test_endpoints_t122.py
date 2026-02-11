"""Integration tests for T122: Test Error Endpoints (Dev-Mode Only).

Tests that the /api/v1/test/error/* endpoints trigger various exception types
and are only available in development mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def app_dev_mode() -> FastAPI:
    """Create a FastAPI app in development mode with test error router."""
    with patch("os.getenv", return_value="development"):
        # Import after patching environment
        from webapp.main import create_app

        app = create_app()
        return app


@pytest.fixture
def app_prod_mode() -> FastAPI:
    """Create a FastAPI app in production mode (test router should not mount)."""
    with patch("os.getenv", return_value="production"):
        # Import after patching environment
        from webapp.main import create_app

        app = create_app()
        return app


@pytest.mark.asyncio
@pytest.mark.integration
class TestErrorEndpointsDevelopmentMode:
    """Test error endpoints are available and work in development mode."""

    async def test_404_endpoint_raises_not_found_error(self, app_dev_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/404 raises NotFoundError."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/404")

            assert response.status_code == 404
            data = response.json()
            assert data["error_code"] == "NOT_FOUND"
            assert "message" in data

    async def test_400_endpoint_raises_bad_request_error(self, app_dev_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/400 raises BadRequestError."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/400")

            assert response.status_code == 400
            data = response.json()
            assert data["error_code"] == "BAD_REQUEST"
            assert "message" in data

    async def test_409_endpoint_raises_conflict_error(self, app_dev_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/409 raises ConflictError."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/409")

            assert response.status_code == 409
            data = response.json()
            assert data["error_code"] == "CONFLICT"
            assert "message" in data

    async def test_422_endpoint_raises_validation_error(self, app_dev_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/422 raises ValidationError."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/422")

            assert response.status_code == 422
            data = response.json()
            assert data["error_code"] == "VALIDATION_ERROR"
            assert "message" in data

    async def test_500_endpoint_raises_unhandled_exception(self, app_dev_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/500 raises unhandled exception."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/500")

            # Unhandled exceptions are caught by the exception handler
            assert response.status_code == 500
            data = response.json()
            assert data["error_code"] == "INTERNAL_ERROR"
            assert "message" in data

    async def test_endpoints_do_not_require_authentication(self, app_dev_mode: FastAPI) -> None:
        """Test error endpoints don't require authentication (debug endpoints)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_dev_mode), base_url="http://test"
        ) as client:
            # Try without any auth headers - should still work
            response = await client.get("/api/v1/test/error/404")
            # Should get 404 from the endpoint, not 401 from auth
            assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestErrorEndpointsProductionMode:
    """Test error endpoints return 404 in production mode."""

    async def test_404_endpoint_returns_404_in_production(self, app_prod_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/404 returns 404 when ENV != development."""
        async with AsyncClient(
            transport=ASGITransport(app=app_prod_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/404")

            # Router not mounted, so we get 404 from FastAPI
            assert response.status_code == 404

    async def test_400_endpoint_returns_404_in_production(self, app_prod_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/400 returns 404 when ENV != development."""
        async with AsyncClient(
            transport=ASGITransport(app=app_prod_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/400")

            assert response.status_code == 404

    async def test_409_endpoint_returns_404_in_production(self, app_prod_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/409 returns 404 when ENV != development."""
        async with AsyncClient(
            transport=ASGITransport(app=app_prod_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/409")

            assert response.status_code == 404

    async def test_422_endpoint_returns_404_in_production(self, app_prod_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/422 returns 404 when ENV != development."""
        async with AsyncClient(
            transport=ASGITransport(app=app_prod_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/422")

            assert response.status_code == 404

    async def test_500_endpoint_returns_404_in_production(self, app_prod_mode: FastAPI) -> None:
        """Test GET /api/v1/test/error/500 returns 404 when ENV != development."""
        async with AsyncClient(
            transport=ASGITransport(app=app_prod_mode), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/error/500")

            assert response.status_code == 404
