"""Integration tests for gear library toggle endpoint (T97).

Tests the POST /api/v1/library/gear/{gear_model_id}/toggle endpoint
used by the gear detail page checkboxes.
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
class TestGearLibraryToggleEndpoint:
    """Integration tests for gear library toggle endpoint (T97)."""

    async def test_toggle_adds_model_to_library_when_not_present(
        self,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """Verify toggle endpoint adds model to library when not present."""
        # Find a gear model
        result = await db_session.execute(
            select(GearModel)
            .join(Gear, GearModel.gear_id == Gear.id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear_model = result.scalar_one_or_none()
        assert gear_model is not None, "No gear models found"

        # Ensure model is NOT in user's library
        await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == gear_model.id,
            )
        ).scalar_one_or_none()

        existing_user_gear = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == gear_model.id,
            )
        )
        existing = existing_user_gear.scalar_one_or_none()
        if existing:
            await db_session.delete(existing)
            await db_session.commit()

        # Call toggle endpoint
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/library/gear/{gear_model.id}/toggle",
                headers={"Authorization": f"Bearer {test_user.id}"},  # Placeholder auth
            )

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify model is now in library
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == gear_model.id,
            )
        )
        user_gear = result.scalar_one_or_none()
        assert user_gear is not None, "Model should be added to library"

    async def test_toggle_removes_model_from_library_when_present(
        self,
        db_session: AsyncSession,
        test_user,
        make_user_gear,
    ) -> None:
        """Verify toggle endpoint removes model from library when present."""
        # Find a gear model and add to library
        result = await db_session.execute(
            select(GearModel)
            .join(Gear, GearModel.gear_id == Gear.id)
            .where(Gear.is_public.is_(True))
            .limit(1)
        )
        gear_model = result.scalar_one_or_none()
        assert gear_model is not None, "No gear models found"

        # Add model to user's library
        user_gear = await make_user_gear(
            user_id=test_user.id,
            gear_model_id=gear_model.id,
        )
        await db_session.commit()

        # Call toggle endpoint
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/library/gear/{gear_model.id}/toggle",
                headers={"Authorization": f"Bearer {test_user.id}"},  # Placeholder auth
            )

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify model is removed from library
        await db_session.expire_all()
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == gear_model.id,
            )
        )
        user_gear = result.scalar_one_or_none()
        assert user_gear is None, "Model should be removed from library"

    async def test_toggle_returns_401_for_unauthenticated_users(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify toggle endpoint requires authentication."""
        # Find a gear model
        result = await db_session.execute(
            select(GearModel).limit(1)
        )
        gear_model = result.scalar_one_or_none()
        assert gear_model is not None, "No gear models found"

        # Call toggle endpoint without authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/library/gear/{gear_model.id}/toggle",
            )

        # Verify response is 401 Unauthorized
        assert response.status_code == 401, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    async def test_toggle_returns_404_for_nonexistent_model(
        self,
        test_user,
    ) -> None:
        """Verify toggle endpoint returns 404 for nonexistent model IDs."""
        from uuid import uuid4

        fake_model_id = uuid4()

        # Call toggle endpoint with fake model ID
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/library/gear/{fake_model_id}/toggle",
                headers={"Authorization": f"Bearer {test_user.id}"},  # Placeholder auth
            )

        # Verify response is 404 Not Found
        assert response.status_code == 404, \
            f"Expected 404 Not Found, got {response.status_code}"

    async def test_toggle_endpoint_uses_post_method(
        self,
        db_session: AsyncSession,
        test_user,
    ) -> None:
        """Verify toggle endpoint only accepts POST requests."""
        # Find a gear model
        result = await db_session.execute(
            select(GearModel).limit(1)
        )
        gear_model = result.scalar_one_or_none()
        assert gear_model is not None, "No gear models found"

        # Try GET method (should fail)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/library/gear/{gear_model.id}/toggle",
                headers={"Authorization": f"Bearer {test_user.id}"},
            )

        # Verify response is 405 Method Not Allowed
        assert response.status_code == 405, \
            f"Expected 405 Method Not Allowed, got {response.status_code}"
