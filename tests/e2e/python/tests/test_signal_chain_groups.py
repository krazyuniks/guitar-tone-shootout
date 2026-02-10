"""E2E tests for Signal Chain Group Management UI.

Tests the group management pages and HTMX fragments.
"""

import pytest
from playwright.async_api import Page, expect
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.e2e
class TestSignalChainGroupsE2E:
    """E2E tests for signal chain group management UI."""

    async def test_library_groups_page_loads(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library groups page should load and show groups heading."""
        # Layer 1: UI action
        response = await page.goto(f"{frontend_url}/library/groups")
        assert response is not None and response.status == 200

        # Layer 2: DOM verification
        await expect(
            page.locator('[data-testid="library-groups-page"]')
        ).to_be_visible()

    async def test_library_groups_shows_group_list(
        self, page: Page, db_session, frontend_url: str
    ) -> None:
        """Library groups page should display user's groups with details."""
        # Layer 1: UI action
        await page.goto(f"{frontend_url}/library/groups")

        # Layer 2: DOM verification - check for group list container
        await expect(
            page.locator('[data-testid="group-list"]')
        ).to_be_visible()

        # Check for group items (if any exist)
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        # If groups exist, verify they show required fields
        if count > 0:
            first_group = group_items.first
            await expect(
                first_group.locator('[data-testid="group-name"]')
            ).to_be_visible()
            await expect(
                first_group.locator('[data-testid="group-base-chain"]')
            ).to_be_visible()
            await expect(
                first_group.locator('[data-testid="group-permutation-count"]')
            ).to_be_visible()

    async def test_htmx_fragment_group_list_endpoint(
        self, page: Page, frontend_url: str
    ) -> None:
        """HTMX fragment endpoint GET /api/v1/html/library/groups returns group list."""
        # Layer 1: UI action - load HTMX fragment endpoint directly
        response = await page.goto(f"{frontend_url}/api/v1/html/library/groups")
        assert response is not None and response.status == 200

        # Layer 2: DOM verification - fragment should contain group list HTML
        content = await page.content()
        assert "group-list" in content or "empty-state" in content

    async def test_group_create_form_displays(
        self, page: Page, frontend_url: str
    ) -> None:
        """Group create form should display with all required fields."""
        # Layer 1: UI action
        await page.goto(f"{frontend_url}/library/groups")
        await page.click('[data-testid="create-group-btn"]')

        # Layer 2: DOM verification
        await expect(
            page.locator('[data-testid="group-form"]')
        ).to_be_visible()
        await expect(
            page.locator('[data-testid="group-name-input"]')
        ).to_be_visible()
        await expect(
            page.locator('[data-testid="group-description-input"]')
        ).to_be_visible()
        await expect(
            page.locator('[data-testid="group-base-chain-selector"]')
        ).to_be_visible()
        await expect(
            page.locator('[data-testid="group-slot-config"]')
        ).to_be_visible()

    async def test_group_edit_form_displays(
        self, page: Page, frontend_url: str
    ) -> None:
        """Group edit form should display with pre-filled values."""
        # Layer 1: UI action - navigate to groups page
        await page.goto(f"{frontend_url}/library/groups")

        # Check if any groups exist
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        if count > 0:
            # Click edit button on first group
            await group_items.first.locator('[data-testid="edit-group-btn"]').click()

            # Layer 2: DOM verification
            await expect(
                page.locator('[data-testid="group-form"]')
            ).to_be_visible()
            # Form should have pre-filled name
            name_input = page.locator('[data-testid="group-name-input"]')
            await expect(name_input).to_be_visible()
            await expect(name_input).not_to_have_value("")

    async def test_group_detail_page_shows_slots(
        self, page: Page, db_session, frontend_url: str
    ) -> None:
        """Group detail page should show slot configuration with gear options."""
        # First, create a group in the database for testing
        # Layer 3: Database setup
        result = await db_session.execute(
            text("""
                SELECT id FROM signal_chain_groups LIMIT 1
            """)
        )
        row = result.fetchone()

        if row:
            group_id = row[0]

            # Layer 1: UI action
            response = await page.goto(f"{frontend_url}/library/groups/{group_id}")
            assert response is not None and response.status == 200

            # Layer 2: DOM verification
            await expect(
                page.locator('[data-testid="group-detail-page"]')
            ).to_be_visible()
            await expect(
                page.locator('[data-testid="group-slots"]')
            ).to_be_visible()

            # Check for slot items
            slot_items = page.locator('[data-testid="slot-item"]')
            count = await slot_items.count()

            if count > 0:
                first_slot = slot_items.first
                await expect(
                    first_slot.locator('[data-testid="slot-position"]')
                ).to_be_visible()
                await expect(
                    first_slot.locator('[data-testid="slot-gear-options"]')
                ).to_be_visible()

    async def test_generate_chains_button_displays(
        self, page: Page, frontend_url: str
    ) -> None:
        """Group detail page should show Generate Chains button."""
        # Navigate to groups page
        await page.goto(f"{frontend_url}/library/groups")

        # Check if any groups exist
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        if count > 0:
            # Click on first group to view detail
            await group_items.first.click()

            # Layer 2: DOM verification
            await expect(
                page.locator('[data-testid="generate-chains-btn"]')
            ).to_be_visible()

    async def test_generate_chains_triggers_htmx_post(
        self, page: Page, frontend_url: str
    ) -> None:
        """Generate Chains button should trigger HTMX POST request."""
        # Navigate to groups page
        await page.goto(f"{frontend_url}/library/groups")

        # Check if any groups exist
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        if count > 0:
            # Click on first group to view detail
            await group_items.first.click()

            # Set up request listener
            async with page.expect_request_finished() as request_info:
                # Click Generate Chains button
                await page.click('[data-testid="generate-chains-btn"]')

            request = await request_info.value
            # Should be POST request to generate endpoint
            assert request.method == "POST"
            assert "/generate" in request.url

    async def test_delete_button_displays(
        self, page: Page, frontend_url: str
    ) -> None:
        """Group detail page should show delete button."""
        # Navigate to groups page
        await page.goto(f"{frontend_url}/library/groups")

        # Check if any groups exist
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        if count > 0:
            # Click on first group to view detail
            await group_items.first.click()

            # Layer 2: DOM verification
            await expect(
                page.locator('[data-testid="delete-group-btn"]')
            ).to_be_visible()

    async def test_delete_button_shows_confirmation(
        self, page: Page, frontend_url: str
    ) -> None:
        """Delete button should show confirmation dialog."""
        # Navigate to groups page
        await page.goto(f"{frontend_url}/library/groups")

        # Check if any groups exist
        group_items = page.locator('[data-testid="group-item"]')
        count = await group_items.count()

        if count > 0:
            # Click on first group to view detail
            await group_items.first.click()

            # Click delete button
            await page.click('[data-testid="delete-group-btn"]')

            # Layer 2: DOM verification - confirmation dialog should appear
            await expect(
                page.locator('[data-testid="delete-confirmation"]')
            ).to_be_visible()
            await expect(
                page.locator('[data-testid="confirm-delete-btn"]')
            ).to_be_visible()
            await expect(
                page.locator('[data-testid="cancel-delete-btn"]')
            ).to_be_visible()

    async def test_groups_page_requires_authentication(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Library groups page should require authentication."""
        # Layer 1: UI action - try to access without auth
        response = await guest_page.goto(f"{frontend_url}/library/groups")

        # Should redirect to login or return 401
        assert response is not None
        assert response.status in [401, 302, 303]
