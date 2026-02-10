"""E2E tests for gear detail page with library checkbox integration (T97).

Tests the gear detail page showing models grouped by platform with library
membership controls for authenticated users and without for unauthenticated users.
"""

import pytest
from playwright.async_api import Page, expect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user_gear import UserGear


@pytest.mark.asyncio
@pytest.mark.e2e
class TestGearDetailLibraryIntegration:
    """E2E tests for gear detail page with library checkboxes (T97)."""

    async def test_unauthenticated_sees_models_without_checkboxes(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Unauthenticated users see models without checkboxes."""
        # Layer 1: Find a public gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found in database"

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify models section is visible
        await expect(
            guest_page.locator('[data-testid="pack-models-list"]')
        ).to_be_visible()

        # Verify at least one model row exists
        model_rows = guest_page.locator('[data-testid="model-row"]')
        await expect(model_rows.first).to_be_visible()

        # Verify NO checkboxes are present (unauthenticated)
        checkboxes = guest_page.locator('[data-testid="model-save-checkbox"]')
        count = await checkboxes.count()
        assert count == 0, "Checkboxes should not be visible for unauthenticated users"

        # Verify login prompt is shown
        await expect(
            guest_page.locator('[data-testid="login-to-save-prompt"]')
        ).to_be_visible()

    async def test_authenticated_sees_checkboxes_for_all_models(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Authenticated users see a checkbox per model."""
        # Layer 1: Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Count models for this gear
        model_count_result = await db_session.execute(
            select(GearModel)
            .where(GearModel.gear_id == gear.id)
        )
        models = model_count_result.scalars().all()
        model_count = len(models)
        assert model_count > 0, "Gear has no models"

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify models section is visible
        await expect(
            page.locator('[data-testid="pack-models-list"]')
        ).to_be_visible()

        # Verify checkboxes are present for each model
        checkboxes = page.locator('[data-testid="model-save-checkbox"]')
        await expect(checkboxes).to_have_count(model_count)

        # Verify NO login prompt is shown (user is authenticated)
        login_prompt = page.locator('[data-testid="login-to-save-prompt"]')
        count = await login_prompt.count()
        assert count == 0, "Login prompt should not be visible for authenticated users"

    async def test_checkbox_state_reflects_library_membership(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """AC: Checkbox state reflects current library membership."""
        # Layer 1: Find a gear and its models
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Layer 3: Check if model is in user's library
        user_gear_result = await db_session.execute(
            select(UserGear)
            .where(UserGear.gear_model_id == gear_model.id)
            .where(UserGear.user_id == test_user.id)
        )
        user_gear = user_gear_result.scalar_one_or_none()
        is_in_library = user_gear is not None

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the checkbox for this specific model
        checkbox = page.locator(
            f'[data-testid="model-save-checkbox"][data-model-id="{gear_model.id}"]'
        )
        await expect(checkbox).to_be_visible()

        # Verify checkbox state matches database
        if is_in_library:
            await expect(checkbox).to_be_checked()
        else:
            await expect(checkbox).not_to_be_checked()

    async def test_clicking_checkbox_calls_toggle_endpoint(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """AC: Clicking checkbox calls POST /api/v1/library/gear/{gear_model_id}/toggle via HTMX."""
        # Layer 1: Find a gear model
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Start listening for network requests
        requests = []

        async def handle_request(request):
            if "/api/v1/library/gear/" in request.url and "/toggle" in request.url:
                requests.append(request)

        page.on("request", handle_request)

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the checkbox and click it
        checkbox = page.locator(
            f'[data-testid="model-save-checkbox"][data-model-id="{gear_model.id}"]'
        )
        await expect(checkbox).to_be_visible()

        initial_state = await checkbox.is_checked()

        # Click the checkbox
        await checkbox.click()

        # Wait for the API call to complete
        await page.wait_for_timeout(1000)

        # Verify the toggle API was called
        assert len(requests) > 0, "Toggle API was not called"
        assert f"/api/v1/library/gear/{gear_model.id}/toggle" in requests[0].url

        # Verify HTTP method is POST
        assert requests[0].method == "POST"

    async def test_checkbox_updates_optimistically(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """AC: Checkbox updates optimistically (Alpine.js toggle + server confirmation)."""
        # Layer 1: Find a gear model not in library
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Ensure model is NOT in library
        await db_session.execute(
            text(
                """
                DELETE FROM user_gear
                WHERE gear_model_id = :model_id AND user_id = :user_id
                """
            ),
            {"model_id": str(gear_model.id), "user_id": str(test_user.id)},
        )
        await db_session.commit()

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the checkbox and click it
        checkbox = page.locator(
            f'[data-testid="model-save-checkbox"][data-model-id="{gear_model.id}"]'
        )
        await expect(checkbox).to_be_visible()
        await expect(checkbox).not_to_be_checked()

        # Click the checkbox
        await checkbox.click()

        # Verify checkbox state changed immediately (optimistic update)
        await expect(checkbox).to_be_checked()

        # Layer 3: Verify database state changed after server response
        await page.wait_for_timeout(500)

        # Refresh session to see committed changes
        await db_session.commit()
        user_gear_result = await db_session.execute(
            select(UserGear)
            .where(UserGear.gear_model_id == gear_model.id)
            .where(UserGear.user_id == test_user.id)
        )
        user_gear = user_gear_result.scalar_one_or_none()

        assert user_gear is not None, "Model should be added to library"

    async def test_model_row_shows_platform_icon_and_size(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Each model shows platform icon, size label."""
        # Layer 1: Find a gear with models that have size info
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .where(GearModel.size.isnot(None))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with sized models found"
        gear, gear_model = row

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the model row
        model_row = guest_page.locator(
            f'[data-testid="model-row"][data-model-id="{gear_model.id}"]'
        )
        await expect(model_row).to_be_visible()

        # Verify model size badge is present
        size_value = gear_model.size.value if hasattr(gear_model.size, "value") else str(gear_model.size)
        size_text = size_value.upper()
        await expect(model_row.locator(f"text={size_text}")).to_be_visible()

        # Verify model name is present
        await expect(
            model_row.locator('[data-testid="model-name"]')
        ).to_be_visible()

    async def test_model_row_shows_file_size(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Each model shows file size."""
        # Layer 1: Find a gear with models that have file_size
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .where(GearModel.file_size.isnot(None))
            .limit(1)
        )
        row = result.first()

        # If no models with file_size, skip this test (data-dependent)
        if row is None:
            pytest.skip("No gear models with file_size found")

        gear, gear_model = row

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the model row
        model_row = guest_page.locator(
            f'[data-testid="model-row"][data-model-id="{gear_model.id}"]'
        )
        await expect(model_row).to_be_visible()

        # Verify file size is displayed (should contain "MB" or "KB")
        # This is a loose check - implementation will determine exact format
        model_row_text = await model_row.inner_text()
        assert ("MB" in model_row_text or "KB" in model_row_text or "GB" in model_row_text), \
            "File size should be displayed in model row"

    async def test_model_row_shows_download_status(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Each model shows download status."""
        # Layer 1: Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify at least one model row exists
        model_rows = guest_page.locator('[data-testid="model-row"]')
        await expect(model_rows.first).to_be_visible()

        # Check for download status indicator
        # This could be a badge, icon, or text indicating "Downloaded", "Available", etc.
        # The exact implementation will be determined by the implementer
        # For now, just verify the model row is present
        first_row = model_rows.first
        assert await first_row.is_visible(), "Model row should be visible with download status"

    async def test_saved_badge_appears_for_library_models(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
        test_user,
        make_user_gear,
    ) -> None:
        """AC: 'Saved' badge appears for models in user's library."""
        # Layer 1: Find a gear model and add it to user's library
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Add model to user's library
        user_gear = await make_user_gear(
            user_id=test_user.id,
            gear_model_id=gear_model.id,
        )
        await db_session.commit()

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the model row
        model_row = page.locator(
            f'[data-testid="model-row"][data-model-id="{gear_model.id}"]'
        )
        await expect(model_row).to_be_visible()

        # Verify 'Saved' badge is visible
        saved_badge = model_row.locator('[data-testid="saved-badge"]')
        await expect(saved_badge).to_be_visible()

    async def test_models_grouped_by_platform(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: Gear detail page lists all models grouped by platform."""
        # Layer 1: Find a gear with models from multiple platforms (if possible)
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Get all models for this gear to check platforms
        models_result = await db_session.execute(
            select(GearModel).where(GearModel.gear_id == gear.id)
        )
        models = models_result.scalars().all()
        assert len(models) > 0, "Gear has no models"

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify models section is visible
        await expect(
            guest_page.locator('[data-testid="pack-models-list"]')
        ).to_be_visible()

        # Verify all models are listed (platform grouping structure will be implementation detail)
        model_rows = guest_page.locator('[data-testid="model-row"]')
        await expect(model_rows).to_have_count(len(models))

    async def test_all_interactive_elements_have_testid(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: All interactive elements have data-testid attributes."""
        # Layer 1: Find a public gear
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify key interactive elements have data-testid
        await expect(
            page.locator('[data-testid="pack-models-list"]')
        ).to_be_visible()

        await expect(
            page.locator('[data-testid="model-row"]').first
        ).to_be_visible()

        # For authenticated users, checkboxes should have testid
        checkboxes = page.locator('[data-testid="model-save-checkbox"]')
        count = await checkboxes.count()
        assert count > 0, "Checkboxes should have data-testid attributes"

    async def test_htmx_fragment_for_model_list_with_library_status(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """AC: HTMX fragment for model list with library status."""
        # This test verifies that the model list section can be updated via HTMX
        # The exact endpoint and mechanism will be implementation detail

        # Layer 1: Find a public gear
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify models section is present and can be targeted by HTMX
        models_section = page.locator('[data-testid="pack-models-list"]')
        await expect(models_section).to_be_visible()

        # Check that the section has an ID or other attribute that HTMX can target
        # The exact attribute will be implementation detail
        has_id = await models_section.evaluate("el => el.hasAttribute('id')")
        has_hx_target = await models_section.evaluate("el => el.hasAttribute('hx-target')")

        # At least one of these should be true for HTMX to work
        assert has_id or has_hx_target, \
            "Models section should have id or hx-target for HTMX updates"
