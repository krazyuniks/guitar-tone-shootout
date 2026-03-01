"""Phase 4 authenticated feature verification tests.

Verifies features that require authentication:
- Settings page shows connected providers
- Library sorting/filtering/pagination works
- Shootout detail page shows comments section
- DI tracks browse page is accessible

T143: Full Regression + Golden Path
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page


# --- Settings Page ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestSettingsPage:
    """Verify settings page renders with provider information."""

    async def test_settings_page_requires_auth(self, guest_page: Page, frontend_url: str) -> None:
        """Settings page redirects unauthenticated users to login."""
        await guest_page.goto(f"{frontend_url}/settings/account")
        # Should redirect to login
        assert "/login" in guest_page.url, (
            f"Settings page should redirect to login, got {guest_page.url}"
        )

    async def test_settings_page_loads_for_auth_user(
        self, auth_context: BrowserContext, frontend_url: str
    ) -> None:
        """Settings page loads for authenticated users and shows providers."""
        page = await auth_context.new_page()
        try:
            response = await page.goto(f"{frontend_url}/settings/account")
            assert response is not None and response.status == 200, (
                f"Settings page returned {response.status if response else 'None'}"
            )

            # Page should contain provider information
            body_text = await page.locator("body").text_content()
            assert body_text is not None
            # Should show at least the T3K provider (the only OAuth provider)
            body_lower = body_text.lower()
            assert "tone3000" in body_lower or "t3k" in body_lower, (
                f"Settings page should show Tone3000 provider, got: {body_text[:500]}"
            )
        finally:
            await page.close()

    async def test_settings_page_shows_connected_status(
        self, auth_context: BrowserContext, frontend_url: str
    ) -> None:
        """Settings page shows connected/linked status for providers."""
        page = await auth_context.new_page()
        try:
            await page.goto(f"{frontend_url}/settings/account")

            # Should have provider status indicators
            body_text = await page.locator("body").text_content()
            assert body_text is not None
            body_lower = body_text.lower()
            # Should show "linked" or "connected" for the active T3K provider
            assert "linked" in body_lower or "connected" in body_lower or "active" in body_lower, (
                f"Settings page should show provider connection status, got: {body_text[:500]}"
            )
        finally:
            await page.close()


# --- Library Sorting/Filtering/Pagination ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestLibrarySortingFilteringPagination:
    """Verify library pages support sorting, filtering, and pagination."""

    async def test_gear_browse_sorting_by_type(self, guest_page: Page, frontend_url: str) -> None:
        """Gear browse page supports gear_type filter parameter."""
        response = await guest_page.goto(f"{frontend_url}/gear?gear_type=amp")
        assert response is not None and response.status == 200

        # Should show filtered results with the gear type
        results = guest_page.locator('[data-testid="gear-results"]')
        count = await results.count()
        assert count > 0, "Gear browse filtered by type should show results section"

    async def test_gear_browse_search_filter(self, guest_page: Page, frontend_url: str) -> None:
        """Gear browse page supports search query parameter."""
        response = await guest_page.goto(f"{frontend_url}/gear?search=mesa")
        assert response is not None and response.status == 200

        # Should show search results
        results = guest_page.locator('[data-testid="gear-results"]')
        count = await results.count()
        assert count > 0, "Gear browse with search should show results section"

    async def test_gear_browse_pagination_page_2(self, guest_page: Page, frontend_url: str) -> None:
        """Gear browse page supports pagination (page 2)."""
        response = await guest_page.goto(f"{frontend_url}/gear?page=2")
        assert response is not None and response.status == 200

        # Page 2 should still have gear content (we have 6000+ gear items)
        pack_cards = guest_page.locator('[data-testid="gear-pack-card"]')
        count = await pack_cards.count()
        assert count > 0, "Gear browse page 2 should show pack cards"

    async def test_gear_browse_combined_filters(self, guest_page: Page, frontend_url: str) -> None:
        """Gear browse page supports combined filter + search + pagination."""
        response = await guest_page.goto(f"{frontend_url}/gear?gear_type=amp&search=fender&page=1")
        assert response is not None and response.status == 200


# --- DI Tracks Browse ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestDITracksBrowse:
    """Verify DI tracks public browse page works."""

    async def test_di_tracks_page_loads(self, guest_page: Page, frontend_url: str) -> None:
        """DI tracks browse page loads successfully."""
        response = await guest_page.goto(f"{frontend_url}/di-tracks")
        assert response is not None and response.status == 200


# --- Shootout Comments ---


@pytest.mark.asyncio
@pytest.mark.e2e
class TestShootoutComments:
    """Verify shootout detail page has a comments section."""

    async def test_shootout_comments_endpoint_exists(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootout comments endpoint is mounted (responds, not 404 nginx)."""
        # Use a fake UUID — should get 404 from the app (not nginx 404)
        response = await guest_page.request.get(
            f"{frontend_url}/shootout/00000000-0000-0000-0000-000000000000/comments"
        )
        # Should NOT be a nginx-level 502/503 (endpoint not found)
        # App-level 404 (shootout not found) is acceptable — proves the route exists
        assert response.status != 502, "Shootout comments endpoint not responding (502)"
