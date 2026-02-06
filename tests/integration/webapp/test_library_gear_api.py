"""Integration tests for user library gear API endpoints.

Tests for:
- GET /api/v1/library/gear - List user's gear library
- POST /api/v1/library/gear - Add gear to library
- DELETE /api/v1/library/gear/{id} - Remove gear from library

All tests expect the endpoint to exist and return proper responses.
Tests will FAIL with 404 when endpoints don't exist yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for isolation tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_gear(db_session: AsyncSession) -> Gear:
    """Create test gear."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp",
        slug="test-amp",
        gear_type=GearType.AMP,
        description="A test amplifier",
        manufacturer="Test Brand",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.fixture
async def second_gear(db_session: AsyncSession) -> Gear:
    """Create second test gear."""
    gear = Gear(
        id=uuid4(),
        name="Test Pedal",
        slug="test-pedal",
        gear_type=GearType.PEDAL,
        description="A test pedal",
        manufacturer="Test Brand",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with the library router.

    Will fail with ImportError when library.py doesn't exist yet.
    """
    from webapp.api.v1.library import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryGearGetEndpoint:
    """Test cases for GET /api/v1/library/gear endpoint."""

    async def test_get_library_returns_empty_list_for_new_user(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/library/gear returns empty list for new user."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/library/gear")

            # Must return 200 with empty array
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0

    async def test_get_library_returns_users_gear(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Test GET /api/v1/library/gear returns user's gear library."""
        # Add gear to user's library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
            nickname="My Amp",
            is_favourite=True,
        )
        db_session.add(user_gear)
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/library/gear")

            # Must return 200 with gear list
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1

            # Verify gear details
            gear_item = data[0]
            assert gear_item["user_gear_id"] == str(user_gear.id)
            assert gear_item["gear_id"] == str(test_gear.id)
            assert gear_item["nickname"] == "My Amp"
            assert gear_item["is_favourite"] is True
            assert gear_item["gear_name"] == "Test Amp"
            assert gear_item["gear_type"] == GearType.AMP.value

    async def test_get_library_only_returns_current_users_gear(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        test_gear: Gear,
        second_gear: Gear,
    ) -> None:
        """Test GET /api/v1/library/gear only returns current user's gear."""
        # Add gear to test_user's library
        user_gear1 = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
            nickname="Test User Gear",
        )
        db_session.add(user_gear1)

        # Add different gear to other_user's library
        user_gear2 = UserGear(
            id=uuid4(),
            user_id=other_user.id,
            gear_id=second_gear.id,
            nickname="Other User Gear",
        )
        db_session.add(user_gear2)
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Note: This test assumes we're authenticated as test_user
            # The actual auth will be handled by CurrentUser dependency
            response = await client.get("/api/v1/library/gear")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1

            # Should only see test_user's gear
            assert data[0]["user_gear_id"] == str(user_gear1.id)
            assert data[0]["nickname"] == "Test User Gear"


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryGearPostEndpoint:
    """Test cases for POST /api/v1/library/gear endpoint."""

    async def test_post_library_gear_adds_to_library(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Test POST /api/v1/library/gear adds gear to user's library."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/library/gear",
                json={
                    "gear_id": str(test_gear.id),
                    "nickname": "My Test Amp",
                    "is_favourite": False,
                },
            )

            # Must return 201 Created
            assert response.status_code == 201
            data = response.json()
            assert "user_gear_id" in data
            assert data["gear_id"] == str(test_gear.id)
            assert data["nickname"] == "My Test Amp"
            assert data["is_favourite"] is False

            # Verify it was actually saved to database
            result = await db_session.execute(
                select(UserGear).where(UserGear.user_id == test_user.id)
            )
            saved_gear = result.scalar_one()
            assert saved_gear.gear_id == test_gear.id
            assert saved_gear.nickname == "My Test Amp"

    async def test_post_library_gear_prevents_duplicate(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Test POST /api/v1/library/gear prevents adding same gear twice."""
        # Add gear to library first time
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
        )
        db_session.add(user_gear)
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Try to add the same gear again
            response = await client.post(
                "/api/v1/library/gear",
                json={"gear_id": str(test_gear.id)},
            )

            # Must return 409 Conflict
            assert response.status_code == 409
            data = response.json()
            assert "detail" in data
            assert "already in library" in data["detail"].lower()

    async def test_post_library_gear_requires_valid_gear_id(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test POST /api/v1/library/gear validates gear exists."""
        fake_gear_id = uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/library/gear",
                json={"gear_id": str(fake_gear_id)},
            )

            # Must return 404 Not Found
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryGearDeleteEndpoint:
    """Test cases for DELETE /api/v1/library/gear/{id} endpoint."""

    async def test_delete_library_gear_removes_from_library(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Test DELETE /api/v1/library/gear/{id} removes gear from library."""
        # Add gear to library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
        )
        db_session.add(user_gear)
        await db_session.commit()
        user_gear_id = user_gear.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(f"/api/v1/library/gear/{user_gear_id}")

            # Must return 204 No Content
            assert response.status_code == 204

            # Verify it was actually deleted from database
            result = await db_session.execute(
                select(UserGear).where(UserGear.id == user_gear_id)
            )
            assert result.scalar_one_or_none() is None

    async def test_delete_library_gear_only_allows_owner(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        test_gear: Gear,
    ) -> None:
        """Test DELETE /api/v1/library/gear/{id} only allows owner to delete."""
        # Add gear to other_user's library
        user_gear = UserGear(
            id=uuid4(),
            user_id=other_user.id,
            gear_id=test_gear.id,
        )
        db_session.add(user_gear)
        await db_session.commit()
        user_gear_id = user_gear.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Note: This test assumes we're authenticated as test_user
            # trying to delete other_user's gear
            response = await client.delete(f"/api/v1/library/gear/{user_gear_id}")

            # Must return 404 (not 403 to avoid leaking existence)
            assert response.status_code == 404

            # Verify gear was NOT deleted
            result = await db_session.execute(
                select(UserGear).where(UserGear.id == user_gear_id)
            )
            assert result.scalar_one_or_none() is not None

    async def test_delete_nonexistent_gear_returns_404(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test DELETE /api/v1/library/gear/{id} returns 404 for nonexistent gear."""
        fake_id = uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(f"/api/v1/library/gear/{fake_id}")

            # Must return 404 Not Found
            assert response.status_code == 404
