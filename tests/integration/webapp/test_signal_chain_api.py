"""Integration tests for SignalChain API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession
from webapp.auth.dependencies import set_session_override, set_user_override
from webapp.main import create_app


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    """Create second test user for isolation tests."""
    suffix = uuid4().hex[:8]
    user = User(username=f"otheruser_{suffix}", email=f"other_{suffix}@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
def make_saved_user_gear(
    session: AsyncSession,
    make_gear: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, UserGear]]:
    """Create a saved UserGear row backed by real gear."""

    async def _make(
        user: User,
        gear_type: GearType = GearType.FULL_RIG,
    ) -> UserGear:
        gear = await make_gear(gear_type, Platform.NAM, models=1)
        await session.refresh(gear, ["models"])
        user_gear = UserGear(
            id=uuid4(),
            user_id=user.id,
            gear_model_id=gear.models[0].id,
        )
        session.add(user_gear)
        await session.flush()
        await session.refresh(user_gear)
        return user_gear

    return _make


@pytest.fixture
async def client(session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with auth."""
    # Set overrides for testing
    set_session_override(session)
    set_user_override(test_user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    set_session_override(None)
    set_user_override(None)


class TestListSignalChains:
    """Tests for GET /api/signal-chains/."""

    async def test_list_empty(self, client: AsyncClient) -> None:
        """Test listing when user has no chains."""
        # Act
        response = await client.get("/api/signal-chains/")

        # Assert
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_user_chains(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test listing returns only current user's chains."""
        # Arrange - create a chain via API
        user_gear = await make_saved_user_gear(test_user)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Test Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        assert create_response.status_code == 201

        # Act
        response = await client.get("/api/signal-chains/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Chain"

    async def test_list_excludes_other_users_chains(
        self,
        client: AsyncClient,
        session: AsyncSession,
        test_user: User,
        other_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test that listing only returns current user's chains."""
        # Arrange - create chain for other_user by switching override
        other_user_gear = await make_saved_user_gear(other_user)
        set_user_override(other_user)
        await client.post(
            "/api/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(other_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        # Switch back to test_user
        set_user_override(test_user)

        # Act
        response = await client.get("/api/signal-chains/")

        # Assert
        assert response.status_code == 200
        assert response.json() == []  # Should not see other user's chains


class TestCreateSignalChain:
    """Tests for POST /api/signal-chains/."""

    async def test_create_valid_chain(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test creating a valid signal chain."""
        user_gear = await make_saved_user_gear(test_user)

        # Act
        response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "My Chain",
                "description": "Test description",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Chain"
        assert data["description"] == "Test description"
        assert data["platform"] == "nam"
        assert len(data["blocks"]) == 1
        assert data["blocks"][0]["gear_type"] == "full_rig"
        assert "id" in data

    async def test_create_invalid_chain_returns_422(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test creating invalid chain returns 422 validation error."""
        user_gear = await make_saved_user_gear(test_user, GearType.PEDAL)

        # Act - chain with pedal only (no amp)
        response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Invalid Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert "error_code" in data or "detail" in data
        # Should contain validation error details
        assert "NO_AMP" in str(data)

    async def test_create_rejects_other_user_gear(
        self,
        client: AsyncClient,
        other_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test that blocks cannot reference another user's saved gear."""
        other_user_gear = await make_saved_user_gear(other_user)

        response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Cross User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(other_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        assert response.status_code == 404

    async def test_create_requires_authentication(self) -> None:
        """Test that create endpoint requires authentication."""
        # Arrange - client without auth
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as unauth_client:
            # Act
            response = await unauth_client.post(
                "/api/signal-chains/",
                json={
                    "name": "Test",
                    "platform": "nam",
                    "blocks": [],
                },
            )

            # Assert
            assert response.status_code == 401


class TestUpdateSignalChain:
    """Tests for PUT /api/signal-chains/{id}."""

    async def test_update_chain_name(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test updating a chain's name."""
        # Arrange - create chain
        user_gear = await make_saved_user_gear(test_user)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Original",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act
        response = await client.put(
            f"/api/signal-chains/{chain_id}",
            json={
                "name": "Updated",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"

    async def test_update_nonexistent_chain_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        """Test updating nonexistent chain returns 404."""
        # Act
        response = await client.put(
            f"/api/signal-chains/{uuid4()}",
            json={
                "name": "Test",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 404

    async def test_update_to_invalid_state_returns_422(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test updating to invalid state returns 422."""
        # Arrange - create valid chain
        full_rig_user_gear = await make_saved_user_gear(test_user)
        pedal_user_gear = await make_saved_user_gear(test_user, GearType.PEDAL)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Valid",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(full_rig_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act - update to invalid state (no amp)
        response = await client.put(
            f"/api/signal-chains/{chain_id}",
            json={
                "name": "Invalid",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(pedal_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 422

    async def test_update_other_users_chain_returns_404(
        self,
        client: AsyncClient,
        session: AsyncSession,
        test_user: User,
        other_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test that updating another user's chain returns 404."""
        # Arrange - create chain as other_user
        other_user_gear = await make_saved_user_gear(other_user)
        set_user_override(other_user)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(other_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Switch back to test_user
        set_user_override(test_user)

        # Act - try to update other user's chain
        response = await client.put(
            f"/api/signal-chains/{chain_id}",
            json={
                "name": "Hacked",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 404  # Not 403, to avoid leaking existence


class TestDeleteSignalChain:
    """Tests for DELETE /api/signal-chains/{id}."""

    async def test_delete_existing_chain(
        self,
        client: AsyncClient,
        test_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test deleting an existing chain."""
        # Arrange - create chain
        user_gear = await make_saved_user_gear(test_user)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "To Delete",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act
        response = await client.delete(f"/api/signal-chains/{chain_id}")

        # Assert
        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get("/api/signal-chains/")
        assert get_response.json() == []

    async def test_delete_nonexistent_chain_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        """Test deleting nonexistent chain returns 404."""
        # Act
        response = await client.delete(f"/api/signal-chains/{uuid4()}")

        # Assert
        assert response.status_code == 404

    async def test_delete_other_users_chain_returns_404(
        self,
        client: AsyncClient,
        session: AsyncSession,
        test_user: User,
        other_user: User,
        make_saved_user_gear: Callable[..., Coroutine[Any, Any, UserGear]],
    ) -> None:
        """Test that deleting another user's chain returns 404."""
        # Arrange - create chain as other_user
        other_user_gear = await make_saved_user_gear(other_user)
        set_user_override(other_user)
        create_response = await client.post(
            "/api/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(other_user_gear.id),
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Switch back to test_user
        set_user_override(test_user)

        # Act - try to delete other user's chain
        response = await client.delete(f"/api/signal-chains/{chain_id}")

        # Assert
        assert response.status_code == 404  # Not 403, to avoid leaking existence
