"""Integration tests for signal chain list SSR page route.

Tests for GET /library/chains - Signal chain list page
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_chain(db_session: AsyncSession, test_user: User) -> SignalChain:
    """Create test signal chain."""
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain",
        description="A test signal chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.commit()
    await db_session.refresh(chain)
    return chain


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryChainsPageRoute:
    """Test signal chain list page route (/library/chains)."""

    async def test_library_chains_route_returns_html(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify GET /library/chains returns HTML page."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="chains-library"' in html
            assert "Signal Chains" in html or "My Chains" in html or "Chains" in html

    async def test_library_chains_renders_base_layout(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify chain list page extends base layout."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_library_chains_has_create_chain_button(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page has button/link to create a new chain."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have build/create chain button with testid
            assert (
                'data-testid="build-chain-btn"' in html
                or "build-chain" in html
                or "create-chain" in html
                or "new-chain" in html
            )

    async def test_library_chains_has_htmx_attributes(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page uses HTMX for dynamic operations."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have HTMX attributes (hx-get, hx-post, hx-delete, etc.)
            assert (
                "hx-get" in html or "hx-post" in html or "hx-delete" in html or "hx-target" in html
            )

    async def test_library_chains_has_edit_links(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify each chain has link to chain builder for editing."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have edit link or button
            assert (
                'data-testid="edit-chain-btn"' in html
                or "edit-chain" in html
                or "/library/chains/build" in html
            )

    async def test_library_chains_requires_authentication(self, db_session: AsyncSession) -> None:
        """Verify page requires authentication - redirects to login when not authenticated."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        # Do NOT override get_current_user_page - should redirect to login

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            response = await client.get("/library/chains")

            # Should redirect to login (302) when not authenticated
            assert response.status_code == 302


@pytest.mark.asyncio
@pytest.mark.integration
class TestChainListFragments:
    """Test HTMX fragments for chain list operations."""

    async def test_chain_delete_fragment_endpoint_exists(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify DELETE fragment endpoint exists for chain deletion."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Fragment endpoint should exist (may return 405 if not DELETE method)
            # This test verifies the route exists
            response = await client.delete(f"/fragments/chains/{test_chain.id}")

            # Should NOT return 404 - route should exist
            assert response.status_code != 404
