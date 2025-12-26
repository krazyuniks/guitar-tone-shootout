"""Health endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_check(client: AsyncClient) -> None:
    """Test health endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "guitar-tone-shootout"


async def test_readiness_check(client: AsyncClient) -> None:
    """Test readiness endpoint returns ready status."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_root(client: AsyncClient) -> None:
    """Test root endpoint returns API info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Guitar Tone Shootout API"
    assert "version" in data


async def test_docs_available(client: AsyncClient) -> None:
    """Test OpenAPI docs are available."""
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_openapi_schema(client: AsyncClient) -> None:
    """Test OpenAPI schema is available."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Guitar Tone Shootout"
    assert "paths" in data
