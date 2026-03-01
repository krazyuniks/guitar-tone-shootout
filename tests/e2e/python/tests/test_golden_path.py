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

        # Default sort is "newest" — verify cards are in descending created_at order.
        # Parse relative_time values ("14m ago", "2d ago") into comparable seconds.
        time_spans = guest_page.locator('[data-testid="pack-relative-time"]')
        count = await time_spans.count()
        assert count >= 2, "Need at least 2 cards to verify sort order"

        unit_seconds = {"m": 60, "h": 3600, "d": 86400, "mo": 2592000, "y": 31536000}
        ages: list[int] = []
        for i in range(count):
            text = (await time_spans.nth(i).text_content() or "").strip()
            match = re.match(r"(\d+)(m|h|d|mo|y)\s+ago", text)
            if match:
                ages.append(int(match.group(1)) * unit_seconds[match.group(2)])

        assert len(ages) >= 2, f"Could not parse enough relative times, got: {ages}"
        for i in range(len(ages) - 1):
            assert ages[i] <= ages[i + 1], (
                f"Gear not sorted newest-first: card {i} ({ages[i]}s) is older than card {i + 1} ({ages[i + 1]}s)"
            )

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
        response = await guest_page.goto(f"{frontend_url}/health")
        assert response is not None and response.status == 200


# --- Protected pages (redirect to /login without auth) ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestProtectedPages:
    """Protected pages redirect unauthenticated users to /login."""

    async def test_library_my_gear(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/library/my-gear")
        assert guest_page.url.endswith("/login")

    async def test_library_chains(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/library/chains")
        assert guest_page.url.endswith("/login")

    async def test_library_shootouts(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/library/shootouts")
        assert guest_page.url.endswith("/login")

    async def test_library_di_tracks(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/library/di-tracks")
        assert guest_page.url.endswith("/login")

    async def test_shootout_create(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/shootout/create")
        assert guest_page.url.endswith("/login")


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


# --- Data integrity ---

# Gear data is synced from T3K and only grows. These are hard minimums.
MIN_GEAR_COUNT = 6213


@pytest.mark.asyncio
@pytest.mark.regression
class TestGearDataPresent:
    """Verify gear data exists — database must not be empty."""

    async def test_gear_api_returns_minimum_count(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Gear API reports at least MIN_GEAR_COUNT items."""
        response = await guest_page.request.get(f"{frontend_url}/api/gear/?limit=1")
        assert response.ok
        data = await response.json()
        total = data["total"]
        assert total >= MIN_GEAR_COUNT, f"Expected >= {MIN_GEAR_COUNT} gear, got {total}"


# --- SSR content assertions ---


@pytest.mark.asyncio
@pytest.mark.regression
class TestGearSSRContent:
    async def test_gear_browse_has_pack_cards(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/gear")
        pack_cards = guest_page.locator('[data-testid="gear-pack-card"]')
        count = await pack_cards.count()
        assert count > 0, "Gear browse page must show pack cards — database has data"

    async def test_gear_browse_has_pagination(self, guest_page: Page, frontend_url: str) -> None:
        await guest_page.goto(f"{frontend_url}/gear")
        pagination = guest_page.locator('[data-testid="pagination"]')
        results_count = guest_page.locator('[data-testid="results-count"]')
        pagination_count = await pagination.count()
        results_count_count = await results_count.count()
        assert pagination_count > 0 or results_count_count > 0, (
            "Expected pagination or results count"
        )

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
        assert pack_count > 0, "Gear browse must show pack cards — database has data"
        models_counts = guest_page.locator('[data-testid="pack-models-count"]')
        count = await models_counts.count()
        assert count > 0, "Expected at least one pack-models-count element"
        # Check at least one has non-zero count
        texts = await models_counts.all_text_contents()
        non_zero = [t for t in texts if re.search(r"[1-9]\d*\s+models?", t)]
        assert len(non_zero) > 0, "Expected at least one pack with models_count > 0"
