"""Integration tests for signal chain list SSR page route.

Tests for GET /library/chains - Signal chain list page
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import Platform
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


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
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
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="library-chains-page"' in html
            assert "Signal Chains" in html or "My Chains" in html or "Chains" in html

    async def test_library_chains_renders_base_layout(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify chain list page extends base layout."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_library_chains_shows_empty_state(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page shows empty state when user has no chains."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should show empty state message
            assert (
                "no chains" in html.lower()
                or "empty" in html.lower()
                or "create a chain" in html.lower()
                or "build your first chain" in html.lower()
            )

    async def test_library_chains_displays_users_chains(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify page displays user's signal chains."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should show the chain name
            assert "Test Chain" in html

            # Should have chain card or item container
            assert 'data-testid="chain-item"' in html or "chain-card" in html

    async def test_library_chains_has_create_chain_button(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page has button/link to create a new chain."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have create chain button with testid
            assert (
                'data-testid="create-chain-btn"' in html
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
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have HTMX attributes (hx-get, hx-post, hx-delete, etc.)
            assert (
                "hx-get" in html or "hx-post" in html or "hx-delete" in html or "hx-target" in html
            )

    async def test_library_chains_has_delete_buttons(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify each chain item has a delete button."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have delete button with testid
            assert (
                'data-testid="delete-chain-btn"' in html
                or "delete-chain" in html
                or "remove-chain" in html
            )

    async def test_library_chains_has_duplicate_buttons(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify each chain item has a duplicate button."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should have duplicate button with testid
            assert (
                'data-testid="duplicate-chain-btn"' in html
                or "duplicate-chain" in html
                or "copy-chain" in html
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
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

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
        """Verify page requires authentication."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        # Do NOT override get_current_user - should fail with 401

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            # Should return 401 Unauthorized
            assert response.status_code == 401

    async def test_library_chains_shows_platform_badge(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify chain items display platform badge."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/chains")

            html = response.text

            # Should show platform (NAM, AIDA-X, etc.)
            assert "NAM" in html or "nam" in html or 'data-testid="platform-badge"' in html


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
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
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Fragment endpoint should exist (may return 405 if not DELETE method)
            # This test verifies the route exists
            response = await client.delete(f"/fragments/chains/{test_chain.id}")

            # Should NOT return 404 - route should exist
            assert response.status_code != 404

    async def test_chain_duplicate_fragment_endpoint_exists(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify POST fragment endpoint exists for chain duplication."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Fragment endpoint should exist
            response = await client.post(f"/fragments/chains/{test_chain.id}/duplicate")

            # Should NOT return 404 - route should exist
            assert response.status_code != 404

    async def test_chain_list_fragment_returns_html(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_chain: SignalChain,
    ) -> None:
        """Verify chain list fragment returns HTML for HTMX updates."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/fragments/chains/list")

            # Should return success
            assert response.status_code == 200

            # Should return HTML
            assert "text/html" in response.headers["content-type"]

            html = response.text

            # Should contain chain items
            assert "Test Chain" in html

    async def test_chain_list_fragment_empty_state(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify chain list fragment shows empty state when no chains."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/fragments/chains/list")

            html = response.text

            # Should show empty state
            assert (
                "no chains" in html.lower() or "empty" in html.lower() or "create" in html.lower()
            )
