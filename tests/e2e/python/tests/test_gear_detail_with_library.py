"""E2E tests for gear detail page with library checkbox integration.

Tests the gear detail page showing models with library membership controls
for authenticated users (checkboxes) and without for unauthenticated users.
"""

import pytest
from playwright.async_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.e2e
class TestGearDetailPageWithLibrary:
    """E2E tests for gear detail page with library checkboxes."""

    async def test_unauthenticated_user_sees_models_without_checkboxes(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify unauthenticated users see model list without checkboxes."""
        # Layer 1: Find a gear with models in the database
        result = await db_session.execute(
            text("SELECT id, slug FROM gear WHERE is_public = true LIMIT 1")
        )
        row = result.first()
        assert row is not None, "No public gear found in database"
        gear_id, gear_slug = row

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear_slug}")

        # Layer 2: Verify models section is visible
        await expect(
            guest_page.locator('[data-testid="pack-models-list"]')
        ).to_be_visible()

        # Verify at least one model row exists
        model_rows = guest_page.locator('[data-testid="model-row"]')
        await expect(model_rows.first).to_be_visible()

        # Verify NO checkboxes are present (unauthenticated)
        checkboxes = guest_page.locator('[data-testid="model-save-checkbox"]')
        await expect(checkboxes.first).not_to_be_visible(timeout=1000)

        # Verify login prompt is shown
        await expect(
            guest_page.locator('[data-testid="login-to-save-prompt"]')
        ).to_be_visible()

    async def test_authenticated_user_sees_checkboxes_for_all_models(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify authenticated users see a checkbox for each model."""
        # Layer 1: Find a gear with multiple models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Get model count for this gear
        model_count_result = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM gear_models WHERE gear_id = :gear_id"
            ),
            {"gear_id": str(gear.id)},
        )
        model_count = model_count_result.scalar()
        assert model_count > 0, "Gear has no models"

        # TODO: Authenticate the page fixture
        # For now, this test will fail because authentication is not implemented
        # The implementer will need to:
        # 1. Add authentication to the page fixture OR
        # 2. Implement manual login in this test OR
        # 3. Use a different fixture that provides authentication

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
        await expect(
            page.locator('[data-testid="login-to-save-prompt"]')
        ).not_to_be_visible(timeout=1000)

    async def test_checkbox_state_reflects_library_membership(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify checkbox checked state matches UserGear records."""
        # Layer 1: Find a gear and get its first model
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Layer 3: Verify model is NOT in user's library initially
        user_gear_result = await db_session.execute(
            select(UserGear).where(UserGear.gear_model_id == gear_model.id)
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

    async def test_clicking_checkbox_toggles_library_membership(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify clicking checkbox adds/removes model from library via HTMX."""
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

        # Verify checkbox state changed optimistically
        if initial_state:
            await expect(checkbox).not_to_be_checked()
        else:
            await expect(checkbox).to_be_checked()

        # Layer 3: Verify database state changed
        # Wait a moment for the server request to complete
        await page.wait_for_timeout(500)

        # Refresh session to see committed changes
        await db_session.commit()
        user_gear_result = await db_session.execute(
            select(UserGear).where(UserGear.gear_model_id == gear_model.id)
        )
        user_gear = user_gear_result.scalar_one_or_none()

        if initial_state:
            # Was checked, now should be removed from library
            assert user_gear is None, "Model should be removed from library"
        else:
            # Was unchecked, now should be added to library
            assert user_gear is not None, "Model should be added to library"

    async def test_model_row_shows_platform_and_size(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify each model row displays platform and size information."""
        # Layer 1: Find a gear with models
        result = await db_session.execute(
            select(Gear, GearModel)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        row = result.first()
        assert row is not None, "No public gear with models found"
        gear, gear_model = row

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the model row
        model_row = guest_page.locator(
            f'[data-testid="model-row"][data-model-id="{gear_model.id}"]'
        )
        await expect(model_row).to_be_visible()

        # Verify model size badge is present (if model has size)
        if gear_model.size:
            size_text = gear_model.size.value.upper()
            await expect(model_row.locator(f"text={size_text}")).to_be_visible()

        # Verify model name is present
        await expect(
            model_row.locator('[data-testid="model-name"]')
        ).to_be_visible()

    async def test_saved_badge_appears_when_model_in_library(
        self,
        page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify 'Saved' badge appears for models in user's library."""
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

        # Check if model is in library
        user_gear_result = await db_session.execute(
            select(UserGear).where(UserGear.gear_model_id == gear_model.id)
        )
        user_gear = user_gear_result.scalar_one_or_none()
        is_in_library = user_gear is not None

        # Navigate to gear detail page
        await page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Find the model row
        model_row = page.locator(
            f'[data-testid="model-row"][data-model-id="{gear_model.id}"]'
        )
        await expect(model_row).to_be_visible()

        # Verify 'Saved' badge visibility matches library membership
        saved_badge = model_row.locator('[data-testid="saved-badge"]')
        if is_in_library:
            await expect(saved_badge).to_be_visible()
        else:
            await expect(saved_badge).not_to_be_visible(timeout=1000)

    async def test_models_list_shows_all_gear_models(
        self,
        guest_page: Page,
        frontend_url: str,
        db_session: AsyncSession,
    ) -> None:
        """Verify all models for a gear are listed in the models section."""
        # Layer 1: Find a gear with multiple models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Count models for this gear
        model_count_result = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM gear_models WHERE gear_id = :gear_id"
            ),
            {"gear_id": str(gear.id)},
        )
        model_count = model_count_result.scalar()
        assert model_count > 0, "Gear has no models"

        # Navigate to gear detail page
        await guest_page.goto(f"{frontend_url}/gear/{gear.slug}")

        # Layer 2: Verify models list is present
        models_list = guest_page.locator('[data-testid="pack-models-list"]')
        await expect(models_list).to_be_visible()

        # Verify correct number of model rows
        model_rows = guest_page.locator('[data-testid="model-row"]')
        await expect(model_rows).to_have_count(model_count)
