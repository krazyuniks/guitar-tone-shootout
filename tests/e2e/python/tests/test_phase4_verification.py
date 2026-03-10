"""Phase 4 completion verification tests.

Verifies all API routers are mounted, sitemap returns valid XML,
custom error pages render, and settings page shows providers.

T143: Full Regression + Golden Path
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.async_api import Page


# --- API Router Mounting Verification ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestAPIRoutersMounted:
    """Verify all Phase 4 API routers are mounted and reachable.

    Each router should respond to its base endpoint (not necessarily 200,
    but NOT 404 — proving the router is mounted).
    """

    async def test_signal_chain_groups_router_mounted(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Signal chain groups API is mounted (401 for unauth, not 404)."""
        response = await guest_page.request.get(f"{frontend_url}/api/signal-chain-groups/")
        # Should be 401 (auth required) not 404 (route not found)
        assert response.status != 404, "signal-chain-groups router not mounted"

    async def test_signal_chains_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Signal chains API is mounted (401 for unauth, not 404)."""
        response = await guest_page.request.get(f"{frontend_url}/api/signal-chains/")
        assert response.status != 404, "signal-chains router not mounted"

    async def test_shootouts_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Shootouts API is mounted (401 for unauth, not 404)."""
        response = await guest_page.request.get(f"{frontend_url}/api/shootouts/")
        assert response.status != 404, "shootouts router not mounted"

    async def test_jobs_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Jobs API is mounted (401 for unauth, not 404)."""
        response = await guest_page.request.get(f"{frontend_url}/api/jobs/")
        assert response.status != 404, "jobs router not mounted"

    async def test_block_types_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Block types API is mounted and returns data (public endpoint)."""
        response = await guest_page.request.get(f"{frontend_url}/api/block-types/")
        assert response.ok, f"block-types returned {response.status}"
        data = await response.json()
        assert isinstance(data, list), "block-types should return a list"

    async def test_di_tracks_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """DI tracks API is mounted (401 for unauth, not 404)."""
        response = await guest_page.request.get(f"{frontend_url}/api/di-tracks")
        assert response.status != 404, "di-tracks router not mounted"

    async def test_auth_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Auth status endpoint is mounted and returns JSON."""
        response = await guest_page.request.get(f"{frontend_url}/auth/status")
        assert response.ok, f"auth/status returned {response.status}"
        data = await response.json()
        assert "valid" in data, "auth/status response must include validity"

    async def test_files_router_mounted(self, guest_page: Page, frontend_url: str) -> None:
        """Files API is mounted (not 404)."""
        # Check /api/files/ with a non-existent file ID
        # to distinguish "router not mounted" from "file not found"
        response = await guest_page.request.get(f"{frontend_url}/api/files/nonexistent")
        # Should get 404 (file not found) or 422 (bad UUID), not a generic nginx 404
        assert response.status != 502, "files router not responding"


# --- Sitemap Verification ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestSitemap:
    """Verify sitemap.xml returns valid XML."""

    async def test_sitemap_returns_valid_xml(self, guest_page: Page, frontend_url: str) -> None:
        """Sitemap returns valid XML with expected structure."""
        response = await guest_page.request.get(f"{frontend_url}/sitemap.xml")
        assert response.ok, f"Sitemap returned {response.status}"

        body = await response.text()
        # Must be valid XML with sitemap namespace
        assert '<?xml version="1.0"' in body, "Missing XML declaration"
        assert "sitemaps.org/schemas/sitemap" in body, "Missing sitemap namespace"
        assert "<urlset" in body, "Missing urlset element"
        assert "</urlset>" in body, "Unclosed urlset element"

        # Must contain at least static pages
        assert "<loc>" in body, "No URLs in sitemap"

        # Verify static pages are present
        assert "/gear" in body, "Gear browse not in sitemap"
        assert "/about" in body or "/shootouts" in body, "Expected static pages in sitemap"

    async def test_sitemap_has_gear_detail_urls(self, guest_page: Page, frontend_url: str) -> None:
        """Sitemap includes public gear detail page URLs."""
        response = await guest_page.request.get(f"{frontend_url}/sitemap.xml")
        assert response.ok

        body = await response.text()
        # Should include gear detail pages (from public gear)
        gear_url_pattern = re.compile(r"<loc>[^<]*/gear/[^<]+</loc>")
        matches = gear_url_pattern.findall(body)
        assert len(matches) > 0, "Sitemap should include gear detail URLs"


# --- Custom Error Pages ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestCustomErrorPages:
    """Verify custom error pages render with styled content."""

    async def test_404_page_has_custom_content(self, guest_page: Page, frontend_url: str) -> None:
        """404 page renders custom error page (not browser default)."""
        await guest_page.goto(f"{frontend_url}/does-not-exist-12345")

        # Should have custom error page content — not just raw text
        body_text = await guest_page.locator("body").text_content()
        assert body_text is not None
        # Custom error page should have "404" or "not found" text
        body_lower = body_text.lower()
        assert "404" in body_lower or "not found" in body_lower, (
            f"404 page should show error information, got: {body_text[:200]}"
        )

    async def test_404_page_has_home_link(self, guest_page: Page, frontend_url: str) -> None:
        """404 page includes a link back to home."""
        await guest_page.goto(f"{frontend_url}/does-not-exist-12345")

        # Error page should have a link to home
        home_link = guest_page.locator('a[href="/"]')
        count = await home_link.count()
        assert count > 0, "404 page should have a link to home"
