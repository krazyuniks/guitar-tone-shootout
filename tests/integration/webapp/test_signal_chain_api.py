"""Integration tests for SignalChain API endpoints."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import set_session_override, set_user_override
from webapp.main import create_app


@pytest.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create test user."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    """Create second test user for isolation tests."""
    user = User(username="otheruser", email="other@example.com")
    session.add(user)
    await session.commit()
    return user


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
    """Tests for GET /api/v1/signal-chains/."""

    async def test_list_empty(self, client: AsyncClient) -> None:
        """Test listing when user has no chains."""
        # Act
        response = await client.get("/api/v1/signal-chains/")

        # Assert
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_user_chains(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test listing returns only current user's chains."""
        # Arrange - create a chain via API
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Test Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )
        assert create_response.status_code == 201

        # Act
        response = await client.get("/api/v1/signal-chains/")

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
    ) -> None:
        """Test that listing only returns current user's chains."""
        # Arrange - create chain for other_user by switching override
        set_user_override(other_user)
        await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )

        # Switch back to test_user
        set_user_override(test_user)

        # Act
        response = await client.get("/api/v1/signal-chains/")

        # Assert
        assert response.status_code == 200
        assert response.json() == []  # Should not see other user's chains


class TestCreateSignalChain:
    """Tests for POST /api/v1/signal-chains/."""

    async def test_create_valid_chain(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test creating a valid signal chain."""
        # Act
        response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "My Chain",
                "description": "Test description",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
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
        assert "id" in data

    async def test_create_invalid_chain_returns_422(
        self,
        client: AsyncClient,
    ) -> None:
        """Test creating invalid chain returns 422 validation error."""
        # Act - chain with pedal only (no amp)
        response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Invalid Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "pedal",
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

    async def test_create_requires_authentication(self) -> None:
        """Test that create endpoint requires authentication."""
        # Arrange - client without auth
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as unauth_client:
            # Act
            response = await unauth_client.post(
                "/api/v1/signal-chains/",
                json={
                    "name": "Test",
                    "platform": "nam",
                    "blocks": [],
                },
            )

            # Assert
            assert response.status_code == 401


class TestUpdateSignalChain:
    """Tests for PUT /api/v1/signal-chains/{id}."""

    async def test_update_chain_name(
        self,
        client: AsyncClient,
    ) -> None:
        """Test updating a chain's name."""
        # Arrange - create chain
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Original",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act
        response = await client.put(
            f"/api/v1/signal-chains/{chain_id}",
            json={
                "name": "Updated",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
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
            f"/api/v1/signal-chains/{uuid4()}",
            json={
                "name": "Test",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
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
    ) -> None:
        """Test updating to invalid state returns 422."""
        # Arrange - create valid chain
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Valid",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act - update to invalid state (no amp)
        response = await client.put(
            f"/api/v1/signal-chains/{chain_id}",
            json={
                "name": "Invalid",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "pedal",
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
    ) -> None:
        """Test that updating another user's chain returns 404."""
        # Arrange - create chain as other_user
        set_user_override(other_user)
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
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
            f"/api/v1/signal-chains/{chain_id}",
            json={
                "name": "Hacked",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )

        # Assert
        assert response.status_code == 404  # Not 403, to avoid leaking existence


class TestDeleteSignalChain:
    """Tests for DELETE /api/v1/signal-chains/{id}."""

    async def test_delete_existing_chain(
        self,
        client: AsyncClient,
    ) -> None:
        """Test deleting an existing chain."""
        # Arrange - create chain
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "To Delete",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Act
        response = await client.delete(f"/api/v1/signal-chains/{chain_id}")

        # Assert
        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get("/api/v1/signal-chains/")
        assert get_response.json() == []

    async def test_delete_nonexistent_chain_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        """Test deleting nonexistent chain returns 404."""
        # Act
        response = await client.delete(f"/api/v1/signal-chains/{uuid4()}")

        # Assert
        assert response.status_code == 404

    async def test_delete_other_users_chain_returns_404(
        self,
        client: AsyncClient,
        session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test that deleting another user's chain returns 404."""
        # Arrange - create chain as other_user
        set_user_override(other_user)
        create_response = await client.post(
            "/api/v1/signal-chains/",
            json={
                "name": "Other User Chain",
                "platform": "nam",
                "blocks": [
                    {
                        "user_gear_id": str(uuid4()),
                        "gear_type": "full_rig",
                        "position": 0,
                    }
                ],
            },
        )
        chain_id = create_response.json()["id"]

        # Switch back to test_user
        set_user_override(test_user)

        # Act - try to delete other user's chain
        response = await client.delete(f"/api/v1/signal-chains/{chain_id}")

        # Assert
        assert response.status_code == 404  # Not 403, to avoid leaking existence
