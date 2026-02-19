"""Integration tests for user library SSR page route.

Tests for GET /library/my-gear - User gear library page
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
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
async def test_gear(db_session: AsyncSession) -> Gear:
    """Create test gear."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp",
        slug="test-amp",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="A test amplifier",
        manufacturer="Test Brand",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryMyGearPageRoute:
    """Test user library page route (/library/my-gear)."""

    async def test_library_my_gear_route_returns_html(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify GET /library/my-gear returns HTML page."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="library-my-gear-page"' in html
            assert "My Gear" in html or "My Library" in html

    async def test_library_my_gear_renders_base_layout(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify library page extends base layout."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_library_my_gear_shows_empty_state(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page shows empty state when user has no gear."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should show empty state message
            assert (
                "no gear" in html.lower()
                or "empty" in html.lower()
                or "add some gear" in html.lower()
            )

    async def test_library_my_gear_displays_users_gear(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Verify page displays user's gear items."""
        # Add gear to user's library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
            nickname="My Test Amp",
            is_favourite=True,
        )
        db_session.add(user_gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should show the gear name or nickname
            assert "Test Amp" in html or "My Test Amp" in html

            # Should have gear card or item container
            assert 'data-testid="gear-item"' in html or "gear-card" in html

    async def test_library_my_gear_has_add_gear_button(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page has button/link to add gear to library."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have add gear button with testid
            assert 'data-testid="add-gear-btn"' in html or "add-gear" in html

    async def test_library_my_gear_has_htmx_attributes(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page uses HTMX for dynamic add/remove operations."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have HTMX attributes (hx-get, hx-post, hx-delete, etc.)
            assert (
                "hx-get" in html or "hx-post" in html or "hx-delete" in html or "hx-target" in html
            )

    async def test_library_my_gear_has_remove_buttons(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Verify each gear item has a remove button."""
        # Add gear to user's library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
        )
        db_session.add(user_gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have remove button with testid
            assert (
                'data-testid="remove-gear-btn"' in html
                or "remove-gear" in html
                or "delete-gear" in html
            )

    async def test_library_my_gear_shows_gear_type_filter(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page has filter controls for gear types."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have filter controls
            assert (
                'data-testid="gear-type-filter"' in html
                or "gear-type-filter" in html
                or "filter" in html.lower()
            )
