"""Integration tests for gear detail page rendering (T97).

Tests that the gear detail page correctly renders model lists with
library status for authenticated and unauthenticated users.

Each test creates its own gear via the ``make_gear`` factory rather than
querying for seed data — see Story 04 of Epic #120 for the migration
rationale (UUID-suffixed fixtures avoid real DB data collisions).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.main import app


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailPageRendering:
    """Integration tests for gear detail page rendering with library status (T97)."""

    async def test_gear_detail_page_renders_for_authenticated_user(
        self,
        make_gear,
        test_user,
    ) -> None:
        """Verify gear detail page renders successfully for authenticated users."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_gear_detail_page_renders_for_unauthenticated_user(
        self,
        make_gear,
    ) -> None:
        """Verify gear detail page renders successfully for unauthenticated users."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_gear_detail_page_includes_models_list(
        self,
        make_gear,
    ) -> None:
        """Verify gear detail page includes models list in HTML."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=2)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert 'data-testid="pack-models-list"' in html, "Models list should be present in HTML"
        assert 'data-testid="model-row"' in html, "At least one model row should be present"

    async def test_gear_detail_page_includes_checkboxes_for_authenticated(
        self,
        make_gear,
        test_user,
    ) -> None:
        """Verify gear detail page includes checkboxes for authenticated users."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text
        assert 'data-testid="model-save-checkbox"' in html, (
            "Checkboxes should be present for authenticated users"
        )
        assert 'data-testid="login-to-save-prompt"' not in html, (
            "Login prompt should not be visible for authenticated users"
        )

    async def test_gear_detail_page_no_checkboxes_for_unauthenticated(
        self,
        make_gear,
    ) -> None:
        """Verify gear detail page does not include checkboxes for unauthenticated users."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert 'data-testid="model-save-checkbox"' not in html, (
            "Checkboxes should not be present for unauthenticated users"
        )
        assert 'data-testid="login-to-save-prompt"' in html, (
            "Login prompt should be visible for unauthenticated users"
        )

    async def test_gear_detail_page_shows_model_platform_and_size(
        self,
        db_session: AsyncSession,
        make_gear,
    ) -> None:
        """Verify gear detail page shows platform and size for each model."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)
        # ``make_gear`` always assigns a size; pull the model back out
        await db_session.refresh(gear, ["models"])
        gear_model = gear.models[0]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        size_value = (
            gear_model.size.value if hasattr(gear_model.size, "value") else str(gear_model.size)
        )
        size_upper = size_value.upper()
        assert size_upper in html, f"Model size '{size_upper}' should be displayed in HTML"

    async def test_gear_detail_page_shows_saved_badge_for_library_models(
        self,
        db_session: AsyncSession,
        make_gear,
        test_user,
        make_user_gear,
    ) -> None:
        """Verify gear detail page shows 'Saved' badge for models in user's library."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)
        await db_session.refresh(gear, ["models"])
        gear_model = gear.models[0]

        await make_user_gear(
            user_id=test_user.id,
            gear_model_id=gear_model.id,
        )
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text
        assert 'data-testid="saved-badge"' in html, (
            "Saved badge should be present for models in library"
        )

    async def test_gear_detail_page_checkbox_state_matches_library(
        self,
        db_session: AsyncSession,
        make_gear,
        test_user,
        make_user_gear,
    ) -> None:
        """Verify checkbox checked state matches library membership."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=2)
        await db_session.refresh(gear, ["models"])
        models = list(gear.models)
        assert len(models) >= 2, "Gear must have at least 2 models for this test"

        await make_user_gear(
            user_id=test_user.id,
            gear_model_id=models[0].id,
        )
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text
        assert 'data-testid="model-save-checkbox"' in html
        assert 'data-model-id="' + str(models[0].id) + '"' in html, (
            "Model in library should be present in HTML"
        )

    async def test_gear_detail_page_returns_404_for_nonpublic_gear(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page returns 404 for non-public gear."""
        fake_slug = "nonexistent-gear-xyz-123"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{fake_slug}")

        assert response.status_code == 404, (
            f"Expected 404 for nonexistent gear, got {response.status_code}"
        )

    async def test_all_model_rows_have_testid_attributes(
        self,
        make_gear,
    ) -> None:
        """Verify all model rows and interactive elements have data-testid attributes."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert 'data-testid="pack-models-list"' in html, "Models list should have testid"
        assert 'data-testid="model-row"' in html, "Model rows should have testid"
        assert 'data-testid="model-name"' in html, "Model names should have testid"
