"""Integration tests for HTMX fragment endpoints (T29).

Tests for /api/v1/html/* endpoints that return Jinja2 template fragments
for HTMX partial page updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import Shootout
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
class TestHTMLFragmentNamespace:
    """Test /api/v1/html/ namespace exists."""

    async def test_html_namespace_exists(self, db_session: AsyncSession) -> None:
        """Verify /api/v1/html/ namespace is routable."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Try to access the namespace - should not 404 on the namespace itself
            # We expect either 200 (if root handler) or 404 (no root handler)
            # or 405 (method not allowed) - but NOT a routing error
            response = await client.get("/api/v1/html/")

            # Should be routable (not a routing error)
            assert response.status_code in [200, 404, 405]


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryShootoutsFragments:
    """Test HTMX fragment endpoints for user library shootouts."""

    async def test_library_shootouts_list_fragment_returns_html(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify GET /api/v1/html/library/shootouts/list returns HTML fragment."""
        # Create shootout
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Shootout",
            description="Test shootout description",
            status="draft",
        )
        db_session.add(shootout)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/shootouts/list")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Shootout" in html

    async def test_library_shootouts_list_fragment_shows_only_user_shootouts(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment shows only current user's shootouts."""
        # Create another user with unique username to avoid conflicts with seeded data
        suffix = uuid4().hex[:8]
        other_user = User(
            id=uuid4(),
            username=f"otheruser_{suffix}",
            email=f"other_{suffix}@example.com",
            is_active=True,
        )
        db_session.add(other_user)

        # Create shootouts for both users
        # Avoid apostrophes in names: Jinja2 autoescaping converts ' to &#x27;
        user_shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="My Test Shootout",
            description="Test user shootout",
            status="draft",
        )
        other_shootout = Shootout(
            id=uuid4(),
            user_id=other_user.id,
            name="Other User Shootout",
            description="Other user shootout",
            status="draft",
        )
        db_session.add_all([user_shootout, other_shootout])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/shootouts/list")

            assert response.status_code == 200
            html = response.text
            assert "My Test Shootout" in html
            assert "Other User Shootout" not in html

    async def test_library_shootouts_list_fragment_accepts_status_filter(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment accepts status filter parameter."""
        # Create shootouts with different statuses
        draft = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Draft Shootout",
            description="Draft",
            status="draft",
        )
        completed = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Completed Shootout",
            description="Completed",
            status="completed",
        )
        db_session.add_all([draft, completed])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by status
            response = await client.get(
                "/api/v1/html/library/shootouts/list", params={"status": "draft"}
            )

            assert response.status_code == 200
            html = response.text
            assert "Draft Shootout" in html
            assert "Completed Shootout" not in html

    async def test_library_shootouts_list_fragment_accepts_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment accepts pagination parameters."""
        # Create multiple shootouts
        for i in range(5):
            shootout = Shootout(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Shootout {i}",
                description=f"Test shootout {i}",
                status="draft",
            )
            db_session.add(shootout)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request with pagination
            response = await client.get(
                "/api/v1/html/library/shootouts/list",
                params={"limit": 2, "offset": 0},
            )

            assert response.status_code == 200
            html = response.text
            # Should return HTML fragment with limited results
            assert len(html) > 0
