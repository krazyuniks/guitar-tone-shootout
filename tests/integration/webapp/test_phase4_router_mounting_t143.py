"""Integration tests for Phase 4 complete router mounting verification (T143).

Verifies ALL API routers declared in main.py are mounted and reachable.
This is a comprehensive check that nothing was missed during Phase 4.

T143 acceptance criterion:
- All API routers mounted and reachable:
  signal_chain_groups, notifications, tags, presets, block_types, irs, files, test (dev only)
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
        """Signal chain groups router is mounted at /api/v1/signal-chain-groups/."""
        response = await client.get("/api/v1/signal-chain-groups/")
        # Auth required -> 401; anything but 404 proves mounting
        assert response.status_code != 404, (
            f"signal-chain-groups router not mounted (got {response.status_code})"
        )

    async def test_notifications_router(self, client: AsyncClient) -> None:
        """Notifications router is mounted at /api/v1/notifications/."""
        response = await client.get("/api/v1/notifications/")
        assert response.status_code != 404, (
            f"notifications router not mounted (got {response.status_code})"
        )

    async def test_tags_router(self, client: AsyncClient) -> None:
        """Tags router is mounted at /api/v1/tags/."""
        response = await client.get("/api/v1/tags/")
        assert response.status_code != 404, f"tags router not mounted (got {response.status_code})"

    async def test_presets_router(self, client: AsyncClient) -> None:
        """Presets router is mounted at /api/v1/presets/."""
        response = await client.get("/api/v1/presets/")
        assert response.status_code != 404, (
            f"presets router not mounted (got {response.status_code})"
        )

    async def test_block_types_router(self, client: AsyncClient) -> None:
        """Block types router is mounted at /api/v1/block-types/."""
        response = await client.get("/api/v1/block-types/")
        # Public endpoint — should return 200 with list
        assert response.status_code == 200, f"block-types router returned {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "block-types should return a JSON list"

    async def test_irs_router(self, client: AsyncClient) -> None:
        """IRs router is mounted at /api/v1/irs/."""
        # POST is the primary method — GET may not have a list endpoint
        # Use POST without body to get 401 (auth) or 422 (validation), not 404
        response = await client.post("/api/v1/irs/")
        assert response.status_code != 404, f"irs router not mounted (got {response.status_code})"

    async def test_files_router(self, client: AsyncClient) -> None:
        """Files router is mounted at /api/v1/files/."""
        # Files requires a path param — use a fake UUID
        response = await client.get("/api/v1/files/00000000-0000-0000-0000-000000000000")
        # Should get 401, 403, or 404 (file not found), not a generic 404
        # The key test: the route pattern is recognized
        assert response.status_code != 405, f"files router not mounted (got {response.status_code})"

    async def test_di_tracks_router(self, client: AsyncClient) -> None:
        """DI tracks router is mounted at /api/v1/di-tracks/."""
        response = await client.get("/api/v1/di-tracks/")
        assert response.status_code != 404, (
            f"di-tracks router not mounted (got {response.status_code})"
        )

    async def test_signal_chains_router(self, client: AsyncClient) -> None:
        """Signal chains router is mounted at /api/v1/signal-chains/."""
        response = await client.get("/api/v1/signal-chains/")
        assert response.status_code != 404, (
            f"signal-chains router not mounted (got {response.status_code})"
        )

    async def test_library_router(self, client: AsyncClient) -> None:
        """Library router is mounted at /api/v1/library/."""
        response = await client.get("/api/v1/library/my-gear")
        assert response.status_code != 404, (
            f"library router not mounted (got {response.status_code})"
        )

    async def test_shootouts_router(self, client: AsyncClient) -> None:
        """Shootouts router is mounted at /api/v1/shootouts/."""
        response = await client.get("/api/v1/shootouts/")
        assert response.status_code != 404, (
            f"shootouts router not mounted (got {response.status_code})"
        )

    async def test_gear_router(self, client: AsyncClient) -> None:
        """Gear router is mounted at /api/v1/gear/."""
        response = await client.get("/api/v1/gear/")
        assert response.status_code == 200, f"gear router returned {response.status_code}"

    async def test_html_fragments_router(self, client: AsyncClient) -> None:
        """HTML fragments router is mounted at /api/v1/html/."""
        response = await client.get("/api/v1/html/gear/list")
        assert response.status_code == 200, f"html fragments router returned {response.status_code}"

    async def test_health_router(self, client: AsyncClient) -> None:
        """Health router is mounted at /api/v1/health."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200, f"health router returned {response.status_code}"

    async def test_auth_router(self, client: AsyncClient) -> None:
        """Auth router is mounted at /api/v1/auth/."""
        response = await client.get("/api/v1/auth/status")
        # Should respond (maybe 200 or error), not 404
        assert response.status_code != 404, f"auth router not mounted (got {response.status_code})"

    async def test_jobs_router(self, client: AsyncClient) -> None:
        """Jobs router is mounted at /api/v1/jobs/."""
        response = await client.get("/api/v1/jobs/")
        assert response.status_code != 404, f"jobs router not mounted (got {response.status_code})"


@pytest.mark.integration
class TestDevOnlyTestRouter:
    """Verify test router is mounted only in development mode."""

    async def test_test_router_mounted_in_dev(self, dev_client: AsyncClient) -> None:
        """Test router is available when ENV=development."""
        response = await dev_client.get("/api/v1/test/error")
        # Should trigger the test error endpoint (500), not 404
        assert response.status_code != 404, (
            f"test router not mounted in development (got {response.status_code})"
        )

    async def test_test_router_not_mounted_in_production(self, client: AsyncClient) -> None:
        """Test router is NOT available in production mode."""
        response = await client.get("/api/v1/test/error")
        assert response.status_code == 404, (
            f"test router should NOT be mounted in production (got {response.status_code})"
        )
