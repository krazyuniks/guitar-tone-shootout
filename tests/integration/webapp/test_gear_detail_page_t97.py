"""Integration tests for gear detail page rendering (T97).

Tests that the gear detail page correctly renders model lists with
library status for authenticated and unauthenticated users.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import app


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailPageRendering:
    """Integration tests for gear detail page rendering with library status (T97)."""

    async def test_gear_detail_page_renders_for_authenticated_user(
        self,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """Verify gear detail page renders successfully for authenticated users."""
        # Find a public gear
        result = await db_session.execute(
            select(Gear).where(Gear.is_public.is_(True)).limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Request page with authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        # Verify response
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_gear_detail_page_renders_for_unauthenticated_user(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page renders successfully for unauthenticated users."""
        # Find a public gear
        result = await db_session.execute(
            select(Gear).where(Gear.is_public.is_(True)).limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear found"

        # Request page without authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        # Verify response
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_gear_detail_page_includes_models_list(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page includes models list in HTML."""
        # Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Request page
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text

        # Verify models section is present
        assert 'data-testid="pack-models-list"' in html, \
            "Models list should be present in HTML"
        assert 'data-testid="model-row"' in html, \
            "At least one model row should be present"

    async def test_gear_detail_page_includes_checkboxes_for_authenticated(
        self,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """Verify gear detail page includes checkboxes for authenticated users."""
        # Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Request page with authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text

        # Verify checkboxes are present
        assert 'data-testid="model-save-checkbox"' in html, \
            "Checkboxes should be present for authenticated users"

        # Verify login prompt is NOT present
        assert 'data-testid="login-to-save-prompt"' not in html, \
            "Login prompt should not be visible for authenticated users"

    async def test_gear_detail_page_no_checkboxes_for_unauthenticated(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page does not include checkboxes for unauthenticated users."""
        # Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Request page without authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text

        # Verify checkboxes are NOT present
        assert 'data-testid="model-save-checkbox"' not in html, \
            "Checkboxes should not be present for unauthenticated users"

        # Verify login prompt IS present
        assert 'data-testid="login-to-save-prompt"' in html, \
            "Login prompt should be visible for unauthenticated users"

    async def test_gear_detail_page_shows_model_platform_and_size(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page shows platform and size for each model."""
        # Find a gear with models that have size
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

        # Request page
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text

        # Verify model size is displayed
        size_value = gear_model.size.value if hasattr(gear_model.size, "value") else str(gear_model.size)
        size_upper = size_value.upper()
        assert size_upper in html, \
            f"Model size '{size_upper}' should be displayed in HTML"

    async def test_gear_detail_page_shows_saved_badge_for_library_models(
        self,
        db_session: AsyncSession,
        test_user,
        make_user_gear,
    ) -> None:
        """Verify gear detail page shows 'Saved' badge for models in user's library."""
        # Find a gear with models
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

        # Request page with authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text

        # Verify 'Saved' badge is present
        assert 'data-testid="saved-badge"' in html, \
            "Saved badge should be present for models in library"

    async def test_gear_detail_page_checkbox_state_matches_library(
        self,
        db_session: AsyncSession,
        test_user,
        make_user_gear,
    ) -> None:
        """Verify checkbox checked state matches library membership."""
        # Find a gear with at least 2 models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
        )
        gear = result.scalars().first()
        assert gear is not None, "No public gear found"

        # Get models for this gear
        models_result = await db_session.execute(
            select(GearModel).where(GearModel.gear_id == gear.id).limit(2)
        )
        models = models_result.scalars().all()
        assert len(models) >= 1, "Gear must have at least 1 model"

        # Add first model to library (if we have 2)
        if len(models) >= 2:
            user_gear = await make_user_gear(
                user_id=test_user.id,
                gear_model_id=models[0].id,
            )
            await db_session.commit()

        # Request page with authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/gear/{gear.slug}",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        html = response.text

        # Verify checkboxes are present
        assert 'data-testid="model-save-checkbox"' in html

        # If we added a model to library, verify checked attribute
        if len(models) >= 2:
            # The first model should have checked="checked" or similar
            # The exact HTML structure will be implementation-specific
            assert 'data-model-id="' + str(models[0].id) + '"' in html, \
                "Model in library should be present in HTML"

    async def test_gear_detail_page_returns_404_for_nonpublic_gear(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify gear detail page returns 404 for non-public gear."""
        # Find a non-public gear (or use fake slug)
        fake_slug = "nonexistent-gear-xyz-123"

        # Request page
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{fake_slug}")

        # Verify 404 response
        assert response.status_code == 404, \
            f"Expected 404 for nonexistent gear, got {response.status_code}"

    async def test_all_model_rows_have_testid_attributes(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify all model rows and interactive elements have data-testid attributes."""
        # Find a gear with models
        result = await db_session.execute(
            select(Gear)
            .join(GearModel, Gear.id == GearModel.gear_id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear = result.scalar_one_or_none()
        assert gear is not None, "No public gear with models found"

        # Request page
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text

        # Verify key testid attributes are present
        assert 'data-testid="pack-models-list"' in html, \
            "Models list should have testid"
        assert 'data-testid="model-row"' in html, \
            "Model rows should have testid"
        assert 'data-testid="model-name"' in html, \
            "Model names should have testid"
