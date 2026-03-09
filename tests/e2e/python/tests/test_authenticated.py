"""Authenticated E2E tests — require valid auth token.

All tests use `auth_page` fixture (authenticated browser context).
The `verified_auth` fixture gates these tests — they FAIL (not skip)
if auth is invalid or expired.

Browser-only: no DB imports, no internal packages.
"""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.asyncio
class TestAuthenticatedPages:
    """Authenticated pages load without redirect to /login."""

    async def test_my_gear_page_loads(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Library my-gear loads for authenticated user."""
        response = await auth_page.goto(f"{frontend_url}/library/my-gear")
        assert response is not None and response.status == 200
        # Should NOT have been redirected to /login
        assert "/login" not in auth_page.url

    async def test_library_chains_loads(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Library chains page loads for authenticated user."""
        response = await auth_page.goto(f"{frontend_url}/library/chains")
        assert response is not None and response.status == 200
        assert "/login" not in auth_page.url

    async def test_library_shootouts_loads(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Library shootouts page loads for authenticated user."""
        response = await auth_page.goto(f"{frontend_url}/library/shootouts")
        assert response is not None and response.status == 200
        assert "/login" not in auth_page.url

    async def test_library_di_tracks_loads(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Library DI tracks page loads for authenticated user."""
        response = await auth_page.goto(f"{frontend_url}/library/di-tracks")
        assert response is not None and response.status == 200
        assert "/login" not in auth_page.url

    async def test_settings_account_loads(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Settings account page loads with provider info."""
        response = await auth_page.goto(f"{frontend_url}/settings/account")
        assert response is not None and response.status == 200
        assert "/login" not in auth_page.url


@pytest.mark.asyncio
class TestGearDetailAuthenticated:
    """Gear detail page behaviour for authenticated users."""

    async def _get_gear_slug(self, auth_page: Page, frontend_url: str) -> str:
        """Fetch a known gear slug from the browse page."""
        await auth_page.goto(f"{frontend_url}/gear")
        gear_links = auth_page.locator('[data-testid="gear-pack-card"] a[href^="/gear/"]')
        await expect(gear_links.first).to_be_visible()
        href = await gear_links.first.get_attribute("href")
        assert href is not None, "Gear browse must expose a gear detail link"
        return href.rstrip("/").split("/")[-1]

    async def test_gear_detail_shows_checkboxes(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Authenticated user sees enabled save checkboxes."""
        slug = await self._get_gear_slug(auth_page, frontend_url)
        await auth_page.goto(f"{frontend_url}/gear/{slug}")

        checkboxes = auth_page.locator('[data-testid="model-save-checkbox"]')
        count = await checkboxes.count()
        assert count > 0, "Gear detail must show model save checkboxes for auth user"

        # Verify checkboxes are NOT disabled
        first_checkbox = checkboxes.first
        is_disabled = await first_checkbox.is_disabled()
        assert not is_disabled, "Model save checkboxes must not be disabled for auth user"

    async def test_no_login_prompt_for_auth_user(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Login prompt is hidden for authenticated users."""
        slug = await self._get_gear_slug(auth_page, frontend_url)
        await auth_page.goto(f"{frontend_url}/gear/{slug}")

        login_prompt = auth_page.locator('[data-testid="login-to-save-prompt"]')
        count = await login_prompt.count()
        assert count == 0, "Login prompt should not appear for authenticated user"


@pytest.mark.asyncio
class TestModelSaveToggle:
    """Model save/unsave toggle via HTMX."""

    async def _get_gear_slug(self, auth_page: Page, frontend_url: str) -> str:
        """Fetch a known gear slug from the browse page."""
        await auth_page.goto(f"{frontend_url}/gear")
        gear_links = auth_page.locator('[data-testid="gear-pack-card"] a[href^="/gear/"]')
        await expect(gear_links.first).to_be_visible()
        href = await gear_links.first.get_attribute("href")
        assert href is not None, "Gear browse must expose a gear detail link"
        return href.rstrip("/").split("/")[-1]

    async def test_model_save_toggle(
        self, auth_page: Page, frontend_url: str, verified_auth: dict
    ) -> None:
        """Click checkbox to save model, then unsave it."""
        slug = await self._get_gear_slug(auth_page, frontend_url)
        await auth_page.goto(f"{frontend_url}/gear/{slug}")

        # Find first unchecked checkbox
        checkboxes = auth_page.locator('[data-testid="model-save-checkbox"]')
        count = await checkboxes.count()
        assert count > 0, "Need at least one model checkbox to test toggle"

        # Find an unchecked checkbox (try each one)
        target_idx = None
        for i in range(count):
            checkbox = checkboxes.nth(i)
            is_checked = await checkbox.is_checked()
            if not is_checked:
                target_idx = i
                break

        if target_idx is None:
            # All are checked — use first one and toggle differently
            target_idx = 0

        checkbox = checkboxes.nth(target_idx)
        was_checked = await checkbox.is_checked()

        # Click to toggle
        await checkbox.click()

        # Wait for HTMX swap (the model-row gets replaced)
        await auth_page.wait_for_timeout(1000)

        # Re-locate after swap (DOM changed)
        new_checkboxes = auth_page.locator('[data-testid="model-save-checkbox"]')
        new_checkbox = new_checkboxes.nth(target_idx)

        if not was_checked:
            # Was unchecked → now should be checked
            await expect(new_checkbox).to_be_checked()
            # Saved badge should appear in that row
            new_row = new_checkbox.locator("xpath=ancestor::div[@data-testid='model-row']")
            await expect(new_row.locator('[data-testid="saved-badge"]')).to_be_visible()

            # Toggle back (unsave)
            await new_checkbox.click()
            await auth_page.wait_for_timeout(1000)

            final_checkboxes = auth_page.locator('[data-testid="model-save-checkbox"]')
            final_checkbox = final_checkboxes.nth(target_idx)
            await expect(final_checkbox).not_to_be_checked()
        else:
            # Was checked → now should be unchecked
            await expect(new_checkbox).not_to_be_checked()

            # Toggle back (re-save)
            await new_checkbox.click()
            await auth_page.wait_for_timeout(1000)

            final_checkboxes = auth_page.locator('[data-testid="model-save-checkbox"]')
            final_checkbox = final_checkboxes.nth(target_idx)
            await expect(final_checkbox).to_be_checked()
