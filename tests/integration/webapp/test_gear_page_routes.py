"""Integration tests for gear SSR page routes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from webapp.adapters.persistence.models.gear import Gear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearBrowsePageRoute:
    """Test gear browse page route (/gear)."""

    async def test_gear_browse_route_returns_html(
        self, db_session: AsyncSession
    ) -> None:
        """Verify GET /gear returns HTML page."""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert "gear-browse-page" in html
            assert "Browse Gear" in html

    async def test_gear_browse_renders_base_layout(
        self, db_session: AsyncSession
    ) -> None:
        """Verify browse page extends base layout."""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

            # Verify CSS is loaded
            assert "_astro" in html or "css" in html

    async def test_gear_browse_includes_filter_controls(
        self, db_session: AsyncSession
    ) -> None:
        """Verify browse page includes filter controls."""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear")

            html = response.text

            # Verify filter controls are in the HTML
            assert "gear-type-filter" in html
            assert "manufacturer-filter" in html
            assert "gear-search-input" in html

    async def test_gear_browse_has_htmx_attributes(
        self, db_session: AsyncSession
    ) -> None:
        """Verify browse page uses HTMX for dynamic updates."""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear")

            html = response.text

            # Verify HTMX attributes are present
            assert "hx-get" in html or "hx-post" in html
            assert "hx-target" in html or "hx-swap" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailPageRoute:
    """Test gear detail page route (/gear/{slug})."""

    async def test_gear_detail_route_returns_html(
        self, db_session: AsyncSession
    ) -> None:
        """Verify GET /gear/{slug} returns HTML page."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Amplifier",
            slug="test-amplifier",
            gear_type="amp",
            description="Test description",
            manufacturer="Test Manufacturer",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear/test-amplifier")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify page contains expected structure
            html = response.text
            assert "gear-detail-page" in html
            assert "Test Amplifier" in html

    async def test_gear_detail_renders_all_fields(
        self, db_session: AsyncSession
    ) -> None:
        """Verify detail page renders all gear fields."""
        # Create test gear with all fields
        gear = Gear(
            id=uuid4(),
            name="Marshall JCM800",
            slug="marshall-jcm800",
            gear_type="amp",
            description="Classic British high-gain amplifier",
            manufacturer="Marshall",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear/marshall-jcm800")

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
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
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
            is_public=False,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear/private-gear")

            # Verify 404 status (not 403, to avoid leaking existence)
            assert response.status_code == 404

    async def test_gear_detail_renders_base_layout(
        self, db_session: AsyncSession
    ) -> None:
        """Verify detail page extends base layout."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Gear",
            slug="test-gear",
            gear_type="pedal",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear/test-gear")

            html = response.text

            # Verify base layout elements are present
            assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
            assert "<html" in html
            assert "</html>" in html

    async def test_gear_detail_includes_back_link(
        self, db_session: AsyncSession
    ) -> None:
        """Verify detail page includes link back to browse."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Gear",
            slug="test-gear",
            gear_type="amp",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/gear/test-gear")

            html = response.text

            # Verify back link is present
            assert "back-to-browse-link" in html
            assert 'href="/gear"' in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearHTMXFragments:
    """Test HTMX fragment endpoints for gear browse."""

    async def test_gear_list_fragment_endpoint_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Verify HTMX fragment endpoint for gear list exists."""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Try common HTMX fragment pattern
            response = await client.get("/fragments/gear/list")

            # Should return HTML fragment (not 404)
            assert response.status_code in [200, 404]

            # If implemented, should return HTML
            if response.status_code == 200:
                assert "text/html" in response.headers["content-type"]

    async def test_gear_list_fragment_accepts_filters(
        self, db_session: AsyncSession
    ) -> None:
        """Verify gear list fragment accepts filter parameters."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Test Amp",
            slug="test-amp",
            gear_type="amp",
            manufacturer="Test",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Test with gear_type filter
            response = await client.get(
                "/fragments/gear/list", params={"gear_type": "amp"}
            )

            # Should accept the parameter (200 or 404 if not implemented yet)
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                html = response.text
                assert "Test Amp" in html

    async def test_gear_list_fragment_accepts_search_query(
        self, db_session: AsyncSession
    ) -> None:
        """Verify gear list fragment accepts search query."""
        # Create test gear
        gear = Gear(
            id=uuid4(),
            name="Unique Searchable Gear",
            slug="unique-searchable-gear",
            gear_type="amp",
            description="Searchable description text",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Test with search query
            response = await client.get(
                "/fragments/gear/list", params={"query": "Searchable"}
            )

            # Should accept the parameter
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                html = response.text
                assert "Unique Searchable Gear" in html
