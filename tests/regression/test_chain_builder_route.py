"""Regression test: Chain builder route is registered and accessible.

Run with: just test-regression
Pass = Route registered | Fail = Route missing or broken
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import set_session_override, set_user_override
from webapp.main import app


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    set_session_override(None)
    set_user_override(None)


class TestChainBuilderRouteRegistration:
    """Verify chain builder route is registered in FastAPI app."""

    @pytest.mark.asyncio
    async def test_builder_route_exists(self, client: AsyncClient) -> None:
        """GET /library/chains/build should be registered and return 200."""
        response = await client.get("/library/chains/build")

        assert response.status_code == 200, "Chain builder route not registered or broken"

    @pytest.mark.asyncio
    async def test_builder_returns_html(self, client: AsyncClient) -> None:
        """Builder route should return HTML content."""
        response = await client.get("/library/chains/build")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert len(response.text) > 0, "Builder returned empty response"

    @pytest.mark.asyncio
    async def test_builder_template_renders(self, client: AsyncClient) -> None:
        """Builder should successfully render template without errors."""
        response = await client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Basic HTML structure should be present
        assert "html" in html.lower(), "Response is not HTML"

        # Should have some page content (not just error page)
        assert len(html) > 100, "HTML response too short - possible error"


class TestChainBuilderStackIntegration:
    """Verify builder integrates with other stack components."""

    @pytest.mark.asyncio
    async def test_builder_loads_with_base_layout(self, client: AsyncClient) -> None:
        """Builder should extend base layout (CSS, HTMX, Alpine)."""
        response = await client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have base layout components
        has_layout = (
            "/_astro/" in html  # Astro bundled assets
            or "htmx" in html.lower()  # HTMX loaded
            or "alpine" in html.lower()  # Alpine.js loaded
        )
        assert has_layout, "Builder missing base layout components"

    @pytest.mark.asyncio
    async def test_builder_has_testid_for_e2e(self, client: AsyncClient) -> None:
        """Builder should have data-testid for E2E test targeting."""
        response = await client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have testable elements
        assert (
            'data-testid="chain-builder-page"' in html
            or 'data-testid="chain-builder-mount"' in html
            or "chain-builder" in html
        ), "Builder missing data-testid attributes for E2E tests"

    @pytest.mark.asyncio
    async def test_chains_list_links_to_builder(self, client: AsyncClient) -> None:
        """Chains list page should link to builder (navigation integrity)."""
        response = await client.get("/library/chains")

        assert response.status_code == 200
        html = response.text

        assert "/library/chains/build" in html, "Chains list missing link to builder"
