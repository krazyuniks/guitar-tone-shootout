"""Golden path regression tests — one test per webapp route.

Browser-level checks using Playwright. Each route tested exactly once.
Verifies status codes, key content, and SSR rendering.
"""

import re

import pytest
from playwright.async_api import Page, expect


# --- Public pages (200) ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestPublicPages:
    async def test_homepage(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(frontend_url)
        assert response is not None and response.status == 200
        await expect(guest_page.locator("text=Guitar Tone Shootout")).to_be_visible()

    async def test_about(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/about")
        assert response is not None and response.status == 200

    async def test_login(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/login")
        assert response is not None and response.status == 200

    async def test_gear_browse(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/gear")
        assert response is not None and response.status == 200
        await expect(guest_page.locator('[data-testid="gear-browse-page"]')).to_be_visible()

    async def test_gear_browse_filtered(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/gear?gear_type=amp")
        assert response is not None and response.status == 200
        await expect(guest_page.locator('[data-testid="gear-results"]')).to_be_visible()

    async def test_gear_browse_search(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/gear?search=fender")
        assert response is not None and response.status == 200
        await expect(guest_page.locator('[data-testid="gear-results"]')).to_be_visible()

    async def test_gear_browse_paginated(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/gear?page=2")
        assert response is not None and response.status == 200

    async def test_di_tracks(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/di-tracks")
        assert response is not None and response.status == 200

    async def test_shootouts(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/shootouts")
        assert response is not None and response.status == 200


# --- Health endpoints (200) ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestHealth:
    async def test_health(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/health")
        assert response is not None and response.status == 200

    async def test_api_health(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/api/v1/health")
        assert response is not None and response.status == 200


# --- HTMX fragment endpoints (200, public) ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestPublicFragments:
    async def test_di_tracks_results(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/api/v1/html/di-tracks/results")
        assert response is not None and response.status == 200

    async def test_shootouts_sections(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/api/v1/html/shootouts/sections")
        assert response is not None and response.status == 200


# --- Protected pages (401 without auth) ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestProtectedPages:
    """Protected pages return 401 for unauthenticated requests."""

    async def test_library_my_gear(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/library/my-gear")
        assert response is not None and response.status == 401

    async def test_library_chains(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/library/chains")
        assert response is not None and response.status == 401

    async def test_library_shootouts(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/library/shootouts")
        assert response is not None and response.status == 401

    async def test_library_di_tracks(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/library/di-tracks")
        assert response is not None and response.status == 401

    async def test_shootout_create(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/shootout/create")
        assert response is not None and response.status == 401


# --- 404 responses ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestNotFound:
    async def test_gear_nonexistent_slug(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/gear/nonexistent-slug-12345")
        assert response is not None and response.status == 404

    async def test_nonexistent_page(self, guest_page: Page, frontend_url: str) -> None:
        response = await guest_page.goto(f"{frontend_url}/does-not-exist")
        assert response is not None and response.status == 404


# --- SSR content assertions ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestGearSSRContent:
    async def test_gear_browse_has_pack_cards(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/gear")
        pack_cards = guest_page.locator('[data-testid="gear-pack-card"]')
        empty_state = guest_page.locator('[data-testid="empty-state"]')
        # Either pack cards or empty state should be visible
        count = await pack_cards.count()
        empty_count = await empty_state.count()
        assert count > 0 or empty_count > 0

    async def test_gear_browse_has_pagination_or_empty(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/gear")
        pagination = guest_page.locator('[data-testid="pagination"]')
        results_count = guest_page.locator('[data-testid="results-count"]')
        pagination_count = await pagination.count()
        results_count_count = await results_count.count()
        assert pagination_count > 0 or results_count_count > 0

    async def test_gear_browse_no_htmx_loading(self, guest_page: Page, frontend_url: str) -> None:
        """Verify no HTMX loading skeleton — content is SSR."""
        await guest_page.goto(f"{frontend_url}/gear")
        # No hx-trigger="load" (would indicate client-side loading)
        load_triggers = guest_page.locator('[hx-trigger="load"]')
        assert await load_triggers.count() == 0
        # No loading skeletons
        pulse_elements = guest_page.locator(".animate-pulse")
        assert await pulse_elements.count() == 0

    async def test_gear_packs_have_models(self, guest_page: Page, frontend_url: str) -> None:
        """Verify gear packs show non-zero model counts."""
        await guest_page.goto(f"{frontend_url}/gear")
        pack_cards = guest_page.locator('[data-testid="gear-pack-card"]')
        pack_count = await pack_cards.count()
        if pack_count == 0:
            pytest.skip("No gear packs in database — data-dependent test")
        models_counts = guest_page.locator('[data-testid="pack-models-count"]')
        count = await models_counts.count()
        assert count > 0, "Expected at least one pack-models-count element"
        # Check at least one has non-zero count
        texts = await models_counts.all_text_contents()
        non_zero = [t for t in texts if re.search(r"[1-9]\d*\s+models?", t)]
        assert len(non_zero) > 0, "Expected at least one pack with models_count > 0"
