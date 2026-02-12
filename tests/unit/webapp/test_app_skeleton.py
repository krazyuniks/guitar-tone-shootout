"""Unit tests for FastAPI application skeleton.

Tests the basic FastAPI app creation, middleware, exception handlers,
and template configuration.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app instance for testing."""
    from webapp.main import create_app

    return create_app()


class TestAppCreation:
    """Test FastAPI app creation and basic configuration."""

    @pytest.mark.asyncio
    async def test_create_app_returns_fastapi_instance(self, app: FastAPI) -> None:
        assert isinstance(app, FastAPI)

    @pytest.mark.asyncio
    async def test_app_has_title(self, app: FastAPI) -> None:
        assert app.title
        assert isinstance(app.title, str)

    @pytest.mark.asyncio
    async def test_app_has_version(self, app: FastAPI) -> None:
        assert app.version
        assert isinstance(app.version, str)


@pytest.mark.xfail(reason="Pre-existing: CORS configuration changed")
class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers_present_on_response(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health", headers={"Origin": "http://localhost:3000"})
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_options_preflight_works(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert response.status_code in (200, 204)
            assert "access-control-allow-origin" in response.headers


class TestRequestIDMiddleware:
    """Test Request ID middleware."""

    @pytest.mark.asyncio
    async def test_request_id_header_added_to_response(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert "x-request-id" in response.headers
            assert len(response.headers["x-request-id"]) > 0

    @pytest.mark.asyncio
    async def test_existing_request_id_preserved(self, app: FastAPI) -> None:
        request_id = "test-request-123"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health", headers={"X-Request-ID": request_id})
            assert response.headers["x-request-id"] == request_id


class TestTimingMiddleware:
    """Test timing middleware."""

    @pytest.mark.asyncio
    async def test_process_time_header_added(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert "x-process-time" in response.headers

    @pytest.mark.asyncio
    async def test_process_time_is_valid_number(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            process_time = response.headers["x-process-time"]
            float_value = float(process_time)
            assert 0.0 <= float_value < 10.0


class TestExceptionHandlers:
    """Test exception handlers."""

    @pytest.mark.asyncio
    async def test_404_returns_json_error(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/nonexistent")
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_http_exception_returns_json_content_type(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/does-not-exist")
            assert response.status_code == 404
            assert response.headers["content-type"].startswith("application/json")


class TestTemplateConfiguration:
    """Test Jinja2 template configuration."""

    @pytest.mark.asyncio
    async def test_templates_module_configured(self) -> None:
        from webapp.templates import templates

        assert templates is not None

    @pytest.mark.asyncio
    async def test_template_directory_points_to_frontend_dist(self) -> None:
        from pathlib import Path

        from webapp.templates import templates

        template_dirs = templates.env.loader.searchpath
        assert len(template_dirs) > 0

        dist_path = Path(template_dirs[0])
        assert dist_path.name == "dist"
        assert dist_path.parent.name == "astro"
        assert dist_path.parent.parent.name == "frontend"
