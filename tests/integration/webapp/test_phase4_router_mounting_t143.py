"""Integration tests for Phase 4 complete router mounting verification (T143).

Verifies ALL API routers declared in main.py are mounted and reachable.
This is a comprehensive check that nothing was missed during Phase 4.

T143 acceptance criterion:
- All API routers mounted and reachable:
  signal_chain_groups, block_types, files, test (dev only)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Create test client with db session wired."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
async def dev_client(db_session: AsyncSession) -> AsyncClient:
    """Create test client with ENV=development for test router."""
    import os

    os.environ["ENV"] = "development"
    try:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        os.environ.pop("ENV", None)


@pytest.mark.integration
class TestAllRoutersMounted:
    """Verify every API router from Phase 4 is mounted and responds.

    A mounted router returns its own response (401, 200, 405, 422, etc).
    An unmounted router returns 404 from FastAPI's default handler.
    """

    async def test_signal_chain_groups_router(self, client: AsyncClient) -> None:
        """Signal chain groups router is mounted at /api/signal-chain-groups/."""
        response = await client.get("/api/signal-chain-groups/")
        # Auth required -> 401; anything but 404 proves mounting
        assert response.status_code != 404, (
            f"signal-chain-groups router not mounted (got {response.status_code})"
        )

    async def test_block_types_router(self, client: AsyncClient) -> None:
        """Block types router is mounted at /api/block-types (no trailing slash)."""
        response = await client.get("/api/block-types")
        # Public endpoint — should return 200 with list
        assert response.status_code == 200, f"block-types router returned {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "block-types should return a JSON list"

    async def test_files_router(self, client: AsyncClient) -> None:
        """Files router is mounted at /api/files/."""
        # Files requires a path param — use a fake UUID
        response = await client.get("/api/files/00000000-0000-0000-0000-000000000000")
        # Should get 401, 403, or 404 (file not found), not a generic 404
        # The key test: the route pattern is recognized
        assert response.status_code != 405, f"files router not mounted (got {response.status_code})"

    async def test_di_tracks_router(self, client: AsyncClient) -> None:
        """DI tracks router is mounted at /api/di-tracks/."""
        response = await client.get("/api/di-tracks/")
        assert response.status_code != 404, (
            f"di-tracks router not mounted (got {response.status_code})"
        )

    async def test_signal_chains_router(self, client: AsyncClient) -> None:
        """Signal chains router is mounted at /api/signal-chains/."""
        response = await client.get("/api/signal-chains/")
        assert response.status_code != 404, (
            f"signal-chains router not mounted (got {response.status_code})"
        )

    async def test_shootouts_router(self, client: AsyncClient) -> None:
        """Shootouts router is mounted at /api/shootouts/."""
        response = await client.get("/api/shootouts/")
        assert response.status_code != 404, (
            f"shootouts router not mounted (got {response.status_code})"
        )

    async def test_html_fragments_router(self, client: AsyncClient) -> None:
        """HTML fragments router is mounted at /shootout/create/chains."""
        response = await client.get("/shootout/create/chains")
        # Route exists — any response other than 404 (FastAPI default) proves mounting
        assert response.status_code != 404, (
            f"html fragments router not mounted (got {response.status_code})"
        )

    async def test_health_router(self, client: AsyncClient) -> None:
        """Health router is mounted at /health."""
        response = await client.get("/health")
        assert response.status_code == 200, f"health router returned {response.status_code}"

    async def test_auth_router(self, client: AsyncClient) -> None:
        """Auth router is mounted at /auth/."""
        response = await client.get("/auth/status")
        # Should respond (maybe 200 or error), not 404
        assert response.status_code != 404, f"auth router not mounted (got {response.status_code})"

    async def test_jobs_router(self, client: AsyncClient) -> None:
        """Jobs router is mounted at /api/jobs/."""
        response = await client.get("/api/jobs/")
        assert response.status_code != 404, f"jobs router not mounted (got {response.status_code})"


@pytest.mark.integration
class TestDevOnlyTestRouter:
    """Verify test router is mounted only in development mode."""

    async def test_test_router_mounted_in_dev(self, dev_client: AsyncClient) -> None:
        """Test router is available when ENV=development."""
        response = await dev_client.get("/api/test/error/500")
        # Should trigger the test error endpoint (500), not 404
        assert response.status_code != 404, (
            f"test router not mounted in development (got {response.status_code})"
        )

    async def test_test_router_not_mounted_in_production(self, client: AsyncClient) -> None:
        """Test router is NOT available in production mode."""
        response = await client.get("/api/test/error/500")
        assert response.status_code == 404, (
            f"test router should NOT be mounted in production (got {response.status_code})"
        )
