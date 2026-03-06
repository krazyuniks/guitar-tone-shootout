"""Integration tests for user library SSR page route.

Tests for GET /library/my-gear - User gear library page
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.user import User


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
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="my-gear-page"' in html
            assert "My Gear" in html

    async def test_library_my_gear_renders_base_layout(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify library page extends base layout."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_library_my_gear_has_htmx_attributes(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page uses HTMX for dynamic add/remove operations."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have HTMX attributes (hx-get, hx-post, hx-delete, etc.)
            assert (
                "hx-get" in html or "hx-post" in html or "hx-delete" in html or "hx-target" in html
            )

    async def test_library_my_gear_shows_gear_type_filter(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Verify page has filter controls for gear types."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session
        app.dependency_overrides[pages.get_current_user_page] = lambda: test_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/library/my-gear")

            html = response.text

            # Should have filter controls
            assert (
                'data-testid="gear-type-filter"' in html
                or "gear-type-filter" in html
                or "filter" in html.lower()
            )
