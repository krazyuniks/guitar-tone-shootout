"""Integration tests for SignalChainGroupService and /api/v1/signal-chain-groups/ endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.entities.signal_chain_group import SignalChainGroup
from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.signal_chain_groups import (
    router,
    set_session_override,
    set_user_override,
)
from webapp.services.signal_chain_group_service import SignalChainGroupService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with signal chain groups router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for ownership tests."""
    user = User(username="otheruser", email="other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def base_chain(db_session: AsyncSession, test_user: User) -> SignalChain:
    """Create a test signal chain."""
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain",
        platform=Platform.NAM,
        blocks=[],
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


# Service Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainGroupService:
    """Test SignalChainGroupService CRUD operations."""

    async def test_create_group(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test creating a signal chain group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Test Group",
            description="Test description",
            base_chain_id=base_chain.id,
            slot_positions=[0, 1],
            gear_options={0: [uuid4()], 1: [uuid4(), uuid4()]},
        )

        async with db_session.begin():
            created = await service.create(group)

        assert created.id == group.id
        assert created.name == "Test Group"
        assert created.description == "Test description"
        assert created.user_id == test_user.id
        assert created.base_chain_id == base_chain.id
        assert created.slot_positions == [0, 1]
        assert len(created.gear_options[0]) == 1
        assert len(created.gear_options[1]) == 2

    async def test_get_by_id(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test retrieving a group by ID."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Test Group",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        retrieved = await service.get_by_id(group.id)

        assert retrieved is not None
        assert retrieved.id == group.id
        assert retrieved.name == "Test Group"
        assert retrieved.user_id == test_user.id

    async def test_get_by_id_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test get_by_id returns None for non-existent group."""
        service = SignalChainGroupService(db_session)

        result = await service.get_by_id(uuid4())

        assert result is None

    async def test_get_by_user_id(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test retrieving groups by user ID."""
        service = SignalChainGroupService(db_session)

        group1 = SignalChainGroup(
            user_id=test_user.id,
            name="Group 1",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )
        group2 = SignalChainGroup(
            user_id=test_user.id,
            name="Group 2",
            base_chain_id=base_chain.id,
            slot_positions=[1],
            gear_options={1: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group1)
            await service.create(group2)

        groups = await service.get_by_user_id(test_user.id)

        assert len(groups) == 2
        assert {g.name for g in groups} == {"Group 1", "Group 2"}

    async def test_update_group(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test updating a group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Original Name",
            description="Original description",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        # Update the group
        group.name = "Updated Name"
        group.description = "Updated description"

        async with db_session.begin():
            updated = await service.update(group)

        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"

        # Verify persistence
        retrieved = await service.get_by_id(group.id)
        assert retrieved is not None
        assert retrieved.name == "Updated Name"
        assert retrieved.description == "Updated description"

    async def test_delete_group(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test deleting a group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="To Delete",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        # Verify it exists
        assert await service.get_by_id(group.id) is not None

        # Delete
        async with db_session.begin():
            await service.delete(group.id)

        # Verify deletion
        assert await service.get_by_id(group.id) is None


# API Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainGroupAPI:
    """Test /api/v1/signal-chain-groups/ endpoints."""

    async def test_list_groups_returns_users_groups(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test GET /api/v1/signal-chain-groups/ returns user's groups."""
        service = SignalChainGroupService(db_session)

        group1 = SignalChainGroup(
            user_id=test_user.id,
            name="Group 1",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )
        group2 = SignalChainGroup(
            user_id=test_user.id,
            name="Group 2",
            base_chain_id=base_chain.id,
            slot_positions=[1],
            gear_options={1: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group1)
            await service.create(group2)

        response = await authenticated_client.get("/api/v1/signal-chain-groups/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {g["name"] for g in data} == {"Group 1", "Group 2"}

    async def test_create_group_success(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test POST /api/v1/signal-chain-groups/ creates a group."""
        gear_id1 = str(uuid4())
        gear_id2 = str(uuid4())

        payload = {
            "name": "New Group",
            "description": "Test group",
            "base_chain_id": str(base_chain.id),
            "slot_positions": [0, 1],
            "gear_options": {
                "0": [gear_id1],
                "1": [gear_id2],
            },
        }

        response = await authenticated_client.post(
            "/api/v1/signal-chain-groups/", json=payload
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Group"
        assert data["description"] == "Test group"
        assert data["base_chain_id"] == str(base_chain.id)
        assert data["slot_positions"] == [0, 1]
        assert "id" in data
        assert "created_at" in data

    async def test_get_group_by_id_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test GET /api/v1/signal-chain-groups/{id} returns group detail."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Test Group",
            description="Description",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        response = await authenticated_client.get(
            f"/api/v1/signal-chain-groups/{group.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(group.id)
        assert data["name"] == "Test Group"
        assert data["description"] == "Description"

    async def test_get_group_by_id_not_found(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/signal-chain-groups/{id} returns 404 for non-existent group."""
        non_existent_id = uuid4()

        response = await authenticated_client.get(
            f"/api/v1/signal-chain-groups/{non_existent_id}"
        )

        assert response.status_code == 404

    async def test_get_group_by_id_ownership_check(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test GET returns 404 for groups owned by other users."""
        service = SignalChainGroupService(db_session)

        # Create group owned by other_user
        group = SignalChainGroup(
            user_id=other_user.id,
            name="Other's Group",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        # Try to access as test_user (authenticated_client)
        response = await authenticated_client.get(
            f"/api/v1/signal-chain-groups/{group.id}"
        )

        # Should return 404 to avoid leaking existence
        assert response.status_code == 404

    async def test_update_group_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test PUT /api/v1/signal-chain-groups/{id} updates a group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Original",
            description="Original description",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        payload = {
            "name": "Updated",
            "description": "Updated description",
        }

        response = await authenticated_client.put(
            f"/api/v1/signal-chain-groups/{group.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["description"] == "Updated description"

    async def test_update_group_ownership_check(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test PUT returns 404 for groups owned by other users."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=other_user.id,
            name="Other's Group",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        payload = {"name": "Hacked"}

        response = await authenticated_client.put(
            f"/api/v1/signal-chain-groups/{group.id}", json=payload
        )

        assert response.status_code == 404

    async def test_delete_group_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test DELETE /api/v1/signal-chain-groups/{id} deletes a group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="To Delete",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        response = await authenticated_client.delete(
            f"/api/v1/signal-chain-groups/{group.id}"
        )

        assert response.status_code == 204

        # Verify deletion
        retrieved = await service.get_by_id(group.id)
        assert retrieved is None

    async def test_delete_group_ownership_check(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test DELETE returns 404 for groups owned by other users."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=other_user.id,
            name="Other's Group",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        response = await authenticated_client.delete(
            f"/api/v1/signal-chain-groups/{group.id}"
        )

        assert response.status_code == 404

        # Verify group still exists
        retrieved = await service.get_by_id(group.id)
        assert retrieved is not None

    async def test_create_requires_authentication(
        self,
        app: FastAPI,
    ) -> None:
        """Test POST requires authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/signal-chain-groups/",
                json={"name": "Test", "slot_positions": []},
            )

            assert response.status_code == 401
