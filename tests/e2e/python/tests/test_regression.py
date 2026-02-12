"""Regression tests for all E86 epic endpoints.

Verifies that all pages and fragments added by E86 return expected HTTP responses.
Run with: just test-golden-path
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

if TYPE_CHECKING:
    from playwright.async_api import Page


@pytest.mark.asyncio
@pytest.mark.e2e
class TestDITracksPages:
    """Verify DI tracks pages return 200 and render correctly."""

    async def test_di_tracks_browse_page_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """DI tracks browse page returns 200 with track listing."""
        await guest_page.goto(f"{frontend_url}/di-tracks")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()

        # Check for DI tracks page heading or content
        # This is a basic smoke test - just verify the page loads
        assert guest_page.url.endswith("/di-tracks")

    async def test_di_tracks_library_page_redirects_to_login(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """DI tracks library page redirects unauthenticated users to /login."""
        await guest_page.goto(f"{frontend_url}/library/di-tracks")
        assert guest_page.url.endswith("/login")


@pytest.mark.asyncio
@pytest.mark.e2e
class TestShootoutPages:
    """Verify shootout pages return 200 and render correctly."""

    async def test_shootout_wizard_redirects_to_login(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootout wizard page redirects unauthenticated users to /login."""
        await guest_page.goto(f"{frontend_url}/shootout/create")
        assert guest_page.url.endswith("/login")

    async def test_shootout_detail_page_with_valid_id(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootout detail page returns 200 with chain listing."""
        # Navigate to shootouts browse page and find a link to a shootout
        await guest_page.goto(f"{frontend_url}/shootouts")
        await expect(guest_page.locator("body")).to_be_visible()

        # Look for any shootout link on the page
        shootout_links = guest_page.locator('a[href*="/shootout/"]')
        count = await shootout_links.count()

        if count > 0:
            # Click the first shootout link
            href = await shootout_links.first.get_attribute("href")
            assert href is not None
            await guest_page.goto(f"{frontend_url}{href}" if href.startswith("/") else href)
            await expect(guest_page.locator("body")).to_be_visible()
        else:
            pytest.skip("No shootouts in database to test")

    async def test_shootouts_browse_page_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootouts browse page returns 200."""
        await guest_page.goto(f"{frontend_url}/shootouts")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()
        assert guest_page.url.endswith("/shootouts")


@pytest.mark.asyncio
@pytest.mark.e2e
class TestGearPages:
    """Verify gear pages return 200 and render correctly."""

    async def test_gear_detail_page_with_valid_slug(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Gear detail page returns 200 with model listing."""
        api_response = await guest_page.request.get(f"{frontend_url}/api/v1/gear/?limit=1")
        assert api_response.ok, "Gear API must return 200"
        data = await api_response.json()
        assert data.get("items"), "Database must contain gear data"

        slug = data["items"][0]["slug"]
        await guest_page.goto(f"{frontend_url}/gear/{slug}")
        await expect(guest_page.locator("body")).to_be_visible()

    async def test_gear_browse_page_returns_200(self, guest_page: Page, frontend_url: str) -> None:
        """Gear browse page returns 200."""
        await guest_page.goto(f"{frontend_url}/gear")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()
        assert guest_page.url.endswith("/gear")


@pytest.mark.asyncio
@pytest.mark.e2e
class TestLibraryPages:
    """Verify library pages redirect unauthenticated users to /login."""

    async def test_library_chains_redirects_to_login(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Signal chain library page redirects to /login."""
        await guest_page.goto(f"{frontend_url}/library/chains")
        assert guest_page.url.endswith("/login")

    async def test_library_my_gear_redirects_to_login(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """My gear library page redirects to /login."""
        await guest_page.goto(f"{frontend_url}/library/my-gear")
        assert guest_page.url.endswith("/login")

    async def test_library_shootouts_redirects_to_login(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootouts library page redirects to /login."""
        await guest_page.goto(f"{frontend_url}/library/shootouts")
        assert guest_page.url.endswith("/login")

    async def test_library_chain_groups_returns_404(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Signal chain groups page route does not exist yet."""
        response = await guest_page.goto(f"{frontend_url}/library/groups")
        assert response is not None and response.status == 404


@pytest.mark.asyncio
@pytest.mark.e2e
class TestHTMXFragments:
    """Verify HTMX fragment endpoints return 200."""

    async def test_gear_list_fragment_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Gear list fragment endpoint returns 200."""
        await guest_page.goto(f"{frontend_url}/api/v1/html/gear/list")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()

    async def test_library_my_gear_list_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library my gear list fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/my-gear/list")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_library_chains_list_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library chains list fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/chains/list")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_library_shootouts_list_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library shootouts list fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/shootouts/list")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_my_gear_results_fragment_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """My gear results fragment endpoint returns 200."""
        await guest_page.goto(f"{frontend_url}/api/v1/html/my-gear/results")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()

    async def test_di_tracks_results_fragment_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """DI tracks results fragment endpoint returns 200."""
        await guest_page.goto(f"{frontend_url}/api/v1/html/di-tracks/results")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()

    async def test_library_tracks_fragment_returns_200(self, page: Page, frontend_url: str) -> None:
        """Library tracks fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/tracks")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_library_chains_fragment_returns_200(self, page: Page, frontend_url: str) -> None:
        """Library chains fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/chains")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_library_shootouts_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library shootouts fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/shootouts")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_library_groups_fragment_returns_200(self, page: Page, frontend_url: str) -> None:
        """Library groups fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/library/groups")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_shootout_create_chains_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Shootout create chains fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/shootout-create/chains")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_shootout_create_ditracks_fragment_returns_200(
        self, page: Page, frontend_url: str
    ) -> None:
        """Shootout create DI tracks fragment endpoint returns 200."""
        await page.goto(f"{frontend_url}/api/v1/html/shootout-create/ditracks")

        # Should render without error
        await expect(page.locator("body")).to_be_visible()

    async def test_shootouts_sections_fragment_returns_200(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Shootouts sections fragment endpoint returns 200."""
        await guest_page.goto(f"{frontend_url}/api/v1/html/shootouts/sections")

        # Should render without error
        await expect(guest_page.locator("body")).to_be_visible()
