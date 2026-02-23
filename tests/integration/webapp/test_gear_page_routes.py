"""Integration tests for gear SSR page routes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearBrowsePageRoute:
    """Test gear browse page route (/gear)."""

    async def test_gear_browse_route_returns_html(self, db_session: AsyncSession) -> None:
        """Verify GET /gear returns HTML page."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert 'data-testid="gear-browse-page"' in html
            assert "Browse Gear" in html

    async def test_gear_browse_renders_base_layout(self, db_session: AsyncSession) -> None:
        """Verify browse page extends base layout."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_gear_browse_includes_filter_controls(self, db_session: AsyncSession) -> None:
        """Verify browse page includes filter controls."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear")

            html = response.text

            # Verify filter controls are in the HTML (using actual template testids)
            assert "filter-amp" in html
            assert "gear-search-form" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailPageRoute:
    """Test gear detail page route (/gear/{slug})."""

    async def test_gear_detail_route_returns_html(self, db_session: AsyncSession) -> None:
        """Verify GET /gear/{slug} returns HTML page."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Amplifier",
            slug="test-amplifier",
            gear_type="amp",
            platform=Platform.NAM,
            description="Test description",
            manufacturer="Test Manufacturer",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear/test-amplifier")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert "gear-detail-page" in html
            assert "Test Amplifier" in html

    async def test_gear_detail_renders_all_fields(self, db_session: AsyncSession) -> None:
        """Verify detail page renders all gear fields."""
        # Use unique slug to avoid conflicts with seeded production data
        slug = f"test-marshall-jcm800-{uuid4().hex[:8]}"
        gear = Gear(
            id=uuid4(),
            name="Marshall JCM800",
            slug=slug,
            gear_type="amp",
            platform=Platform.NAM,
            description="Classic British high-gain amplifier",
            manufacturer="Marshall",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{slug}")

            html = response.text

            # Verify all fields are rendered
            assert "Marshall JCM800" in html
            assert "amp" in html.lower()
            assert "Marshall" in html
            assert "Classic British high-gain amplifier" in html

    async def test_gear_detail_returns_404_for_nonexistent_slug(
        self, db_session: AsyncSession
    ) -> None:
        """Verify 404 response for nonexistent gear slug."""
        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear/nonexistent-slug-12345")

            # Verify 404 status
            assert response.status_code == 404

    async def test_gear_detail_returns_404_for_non_public_gear(
        self, db_session: AsyncSession
    ) -> None:
        """Verify non-public gear returns 404 (hides existence)."""
        # Create non-public gear
        gear = Gear(
            id=uuid4(),
            name="Private Gear",
            slug="private-gear",
            gear_type="amp",
            platform=Platform.NAM,
            is_public=False,
        )
        db_session.add(gear)
        await db_session.commit()

        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear/private-gear")

            # Verify 404 status (not 403, to avoid leaking existence)
            assert response.status_code == 404

    async def test_gear_detail_renders_base_layout(self, db_session: AsyncSession) -> None:
        """Verify detail page extends base layout."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Gear",
            slug="test-gear",
            gear_type="pedal",
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear/test-gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

    async def test_gear_detail_includes_back_link(self, db_session: AsyncSession) -> None:
        """Verify detail page includes link back to browse."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Gear",
            slug="test-gear",
            gear_type="amp",
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        from webapp.api import pages

        app = create_app()
        app.dependency_overrides[pages.get_db_session] = lambda: db_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear/test-gear")

            html = response.text

            # Verify back link to gear browse is present
            assert 'href="/gear"' in html
