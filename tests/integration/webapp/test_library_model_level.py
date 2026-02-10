"""Integration tests for model-level gear library management API.

Tests the library API endpoints that work with gear_model_id instead of gear_id.
Users add/remove individual gear models to their library.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_gear(db_session: AsyncSession) -> Gear:
    """Create a test gear item."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp",
        gear_type=GearType.AMP,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.fixture
async def test_gear_model(
    db_session: AsyncSession, test_gear: Gear
) -> GearModel:
    """Create a test gear model."""
    model = GearModel(
        id=uuid4(),
        gear_id=test_gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


@pytest.fixture
async def second_gear_model(
    db_session: AsyncSession, test_gear: Gear
) -> GearModel:
    """Create a second test gear model for the same gear."""
    model = GearModel(
        id=uuid4(),
        gear_id=test_gear.id,
        platform=Platform.NAM,
        size=ModelSize.LITE,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


@pytest.fixture
async def authenticated_client(db_session: AsyncSession, test_user: User):
    """Create an authenticated async HTTP client."""
    from webapp.auth.dependencies import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryModelLevelAPI:
    """Test suite for model-level library API."""

    async def test_add_gear_model_to_library(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """POST /api/v1/library/gear accepts gear_model_id."""
        response = await authenticated_client.post(
            "/api/v1/library/gear",
            json={"gear_model_id": str(test_gear_model.id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["gear_model_id"] == str(test_gear_model.id)
        assert data["user_gear_id"] is not None

        # Verify database state
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == test_gear_model.id,
            )
        )
        user_gear = result.scalar_one_or_none()
        assert user_gear is not None
        assert user_gear.gear_model_id == test_gear_model.id

    async def test_list_returns_platform_and_size(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """GET /api/v1/library/gear returns platform and size fields."""
        # Add gear model to library first
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=test_gear_model.id,
        )
        db_session.add(user_gear)
        await db_session.commit()

        # List library
        response = await authenticated_client.get("/api/v1/library/gear")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]

        # Verify model-level fields are present
        assert item["gear_model_id"] == str(test_gear_model.id)
        assert item["gear_name"] is not None
        assert item["gear_type"] is not None

        # NEW: platform and size fields must be present
        assert "platform" in item
        assert item["platform"] == Platform.NAM.value
        assert "size" in item
        assert item["size"] == ModelSize.STANDARD.value

    async def test_delete_still_works(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """DELETE /api/v1/library/gear/{user_gear_id} still works."""
        # Add gear model to library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=test_gear_model.id,
        )
        db_session.add(user_gear)
        await db_session.commit()
        user_gear_id = user_gear.id

        # Remove from library
        response = await authenticated_client.delete(
            f"/api/v1/library/gear/{user_gear_id}",
        )

        assert response.status_code == 204

        # Verify database state
        result = await db_session.execute(
            select(UserGear).where(UserGear.id == user_gear_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_toggle_adds_if_not_in_library(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """POST /api/v1/library/gear/{gear_model_id}/toggle adds if not present."""
        # Verify not in library yet
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == test_gear_model.id,
            )
        )
        assert result.scalar_one_or_none() is None

        # Toggle (should add)
        response = await authenticated_client.post(
            f"/api/v1/library/gear/{test_gear_model.id}/toggle",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "added"
        assert data["user_gear_id"] is not None
        assert data["gear_model_id"] == str(test_gear_model.id)

        # Verify database state
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == test_gear_model.id,
            )
        )
        user_gear = result.scalar_one_or_none()
        assert user_gear is not None

    async def test_toggle_removes_if_already_in_library(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """POST /api/v1/library/gear/{gear_model_id}/toggle removes if present."""
        # Add to library first
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=test_gear_model.id,
        )
        db_session.add(user_gear)
        await db_session.commit()
        user_gear_id = user_gear.id

        # Toggle (should remove)
        response = await authenticated_client.post(
            f"/api/v1/library/gear/{test_gear_model.id}/toggle",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "removed"
        assert data["gear_model_id"] == str(test_gear_model.id)

        # Verify database state
        result = await db_session.execute(
            select(UserGear).where(UserGear.id == user_gear_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_toggle_returns_404_for_nonexistent_model(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Toggle endpoint returns 404 for nonexistent gear model."""
        nonexistent_id = uuid4()

        response = await authenticated_client.post(
            f"/api/v1/library/gear/{nonexistent_id}/toggle",
        )

        assert response.status_code == 404

    async def test_unique_constraint_prevents_duplicate(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """Cannot add same gear model to library twice."""
        # Add once
        response = await authenticated_client.post(
            "/api/v1/library/gear",
            json={"gear_model_id": str(test_gear_model.id)},
        )
        assert response.status_code == 201

        # Try to add again
        response = await authenticated_client.post(
            "/api/v1/library/gear",
            json={"gear_model_id": str(test_gear_model.id)},
        )
        assert response.status_code == 409
        assert "already in library" in response.json()["detail"].lower()

    async def test_different_models_same_gear_both_allowed(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
        second_gear_model: GearModel,
    ) -> None:
        """User can add multiple models of the same gear to library."""
        # Add first model
        response = await authenticated_client.post(
            "/api/v1/library/gear",
            json={"gear_model_id": str(test_gear_model.id)},
        )
        assert response.status_code == 201

        # Add second model (same gear, different model)
        response = await authenticated_client.post(
            "/api/v1/library/gear",
            json={"gear_model_id": str(second_gear_model.id)},
        )
        assert response.status_code == 201

        # Verify both are in library
        result = await db_session.execute(
            select(UserGear).where(UserGear.user_id == test_user.id)
        )
        user_gears = result.scalars().all()
        assert len(user_gears) == 2

        model_ids = {ug.gear_model_id for ug in user_gears}
        assert test_gear_model.id in model_ids
        assert second_gear_model.id in model_ids

    async def test_unauthorized_access_rejected(
        self,
        test_gear_model: GearModel,
    ) -> None:
        """All endpoints require authentication."""
        # Create unauthenticated client
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as unauthenticated_client:
            # GET without auth
            response = await unauthenticated_client.get("/api/v1/library/gear")
            assert response.status_code == 401

            # POST without auth
            response = await unauthenticated_client.post(
                "/api/v1/library/gear",
                json={"gear_model_id": str(test_gear_model.id)},
            )
            assert response.status_code == 401

            # DELETE without auth
            response = await unauthenticated_client.delete(
                f"/api/v1/library/gear/{uuid4()}",
            )
            assert response.status_code == 401
