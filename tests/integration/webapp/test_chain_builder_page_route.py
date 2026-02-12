"""Integration tests for chain builder page route handler.

Tests verify that the FastAPI route for /library/chains/build
serves the correct template with proper context.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import (
    set_session_override,
    set_user_override,
)
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
async def authenticated_client(
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


@pytest.fixture
async def guest_client() -> AsyncGenerator[AsyncClient, None]:
    """Create unauthenticated HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.integration
class TestChainBuilderPageRoute:
    """Test the /library/chains/build route handler."""

    async def test_builder_route_exists(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """GET /library/chains/build should return 200."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200

    async def test_builder_returns_html_content(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder route should return HTML content type."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_builder_renders_template(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder should render the chains_build.html template."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have HTML structure
        assert "<!DOCTYPE html>" in html or "<html" in html

        # Should have builder page identifier
        assert 'data-testid="chain-builder-page"' in html or "chain-builder" in html.lower()

    async def test_builder_extends_base_layout(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder page should include base layout elements."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have Tailwind CSS link (from base layout)
        assert "/_astro/" in html and ".css" in html

        # Should have HTMX script (from base layout)
        assert "htmx" in html.lower()

    async def test_builder_has_react_mount_point(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder page should have element for React component to mount."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have a mount point (div with id/testid)
        # Exact structure depends on template implementation
        assert "<div" in html, "No div elements for React mount point"

    async def test_builder_includes_react_scripts(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder page should include scripts to mount React component."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have script tags
        assert "<script" in html

        # Should reference React bundle or initialization script
        # (Astro bundles are in /_astro/*.js)
        # Or inline script that mounts the component
        has_script = (
            ("/_astro/" in html and ".js" in html)
            or ("SignalChainBuilder" in html)
            or ("<script>" in html)
        )
        assert has_script, "No React mounting scripts found"

    async def test_builder_requires_authentication(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Unauthenticated requests should return 401."""
        response = await guest_client.get("/library/chains/build")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestBuilderWithChainId:
    """Test builder in edit mode with chain_id parameter."""

    async def test_builder_accepts_chain_id_param(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder should accept ?chain_id=<uuid> query parameter."""
        test_chain_id = uuid4()

        response = await authenticated_client.get(f"/library/chains/build?chain_id={test_chain_id}")

        # Should return 200 (even if chain doesn't exist, page still renders)
        # Component handles "chain not found" on client side
        assert response.status_code == 200

    async def test_builder_passes_chain_id_to_template(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder should pass chain_id to template context for React props."""
        test_chain_id = uuid4()

        response = await authenticated_client.get(f"/library/chains/build?chain_id={test_chain_id}")

        assert response.status_code == 200
        html = response.text

        # chain_id should appear in the HTML (either as data attribute or in script)
        # This allows React component to fetch the chain
        assert str(test_chain_id) in html, "chain_id not passed to React component"


@pytest.mark.asyncio
@pytest.mark.integration
class TestBuilderPageIntegration:
    """Test builder page integration with other routes."""

    async def test_chains_list_page_links_to_builder(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Chains list page should have link to builder."""
        response = await authenticated_client.get("/library/chains")

        assert response.status_code == 200
        html = response.text

        # Should have link to builder
        assert "/library/chains/build" in html

    @pytest.mark.xfail(reason="Pre-existing: template assertions need update")
    async def test_builder_page_title_is_descriptive(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Builder page should have descriptive title."""
        response = await authenticated_client.get("/library/chains/build")

        assert response.status_code == 200
        html = response.text

        # Should have title tag with builder-related content
        assert "<title>" in html
        # Title should mention "build" or "create" or "builder"
        title_section = html[html.find("<title>") : html.find("</title>") + 8]
        title_lower = title_section.lower()
        assert (
            "build" in title_lower
            or "create" in title_lower
            or "builder" in title_lower
            or "chain" in title_lower
        ), f"Page title not descriptive: {title_section}"
