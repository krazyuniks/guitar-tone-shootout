"""Integration tests for signal chain groups router mounting (T123).

This test verifies that the signal_chain_groups router is properly imported
and mounted in main.py. The router exists and has been tested in isolation,
but it was never connected to the main application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.signal_chain_group import SignalChainGroup
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app
from webapp.services.signal_chain_group_service import SignalChainGroupService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
        blocks=[],
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def unauthenticated_client(
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an unauthenticated HTTP client against the real app."""
    from webapp.auth.dependencies import set_session_override

    set_session_override(db_session)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)


@pytest.fixture
async def authenticated_client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client against the real app."""
    from webapp.auth.dependencies import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainGroupsRouterMount:
    """Test that signal_chain_groups router is mounted in main.py."""

    async def test_list_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/signal-chain-groups/ returns 401 without auth."""
        response = await unauthenticated_client.get("/api/signal-chain-groups/")

        assert response.status_code == 401

    async def test_list_endpoint_returns_200_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test GET /api/signal-chain-groups/ returns 200 with auth."""
        response = await authenticated_client.get("/api/signal-chain-groups/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        base_chain: SignalChain,
    ) -> None:
        """Test POST /api/signal-chain-groups/ returns 401 without auth."""
        payload = {
            "name": "Test Group",
            "base_chain_id": str(base_chain.id),
            "slot_positions": [0],
            "gear_options": {"0": [str(uuid4())]},
        }

        response = await unauthenticated_client.post("/api/signal-chain-groups/", json=payload)

        assert response.status_code == 401

    async def test_create_endpoint_creates_group_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        base_chain: SignalChain,
    ) -> None:
        """Test POST /api/signal-chain-groups/ creates a group."""
        gear_id = str(uuid4())
        payload = {
            "name": "New Group",
            "description": "Test group",
            "base_chain_id": str(base_chain.id),
            "slot_positions": [0],
            "gear_options": {"0": [gear_id]},
        }

        response = await authenticated_client.post("/api/signal-chain-groups/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Group"
        assert data["description"] == "Test group"

    async def test_get_detail_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test GET /api/signal-chain-groups/{id} returns 401 without auth."""
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

        response = await unauthenticated_client.get(f"/api/signal-chain-groups/{group.id}")

        assert response.status_code == 401

    async def test_get_detail_endpoint_returns_group_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test GET /api/signal-chain-groups/{id} returns group detail."""
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

        response = await authenticated_client.get(f"/api/signal-chain-groups/{group.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Group"
        assert data["description"] == "Description"

    async def test_update_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test PUT /api/signal-chain-groups/{id} returns 401 without auth."""
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

        payload = {"name": "Updated"}

        response = await unauthenticated_client.put(
            f"/api/signal-chain-groups/{group.id}", json=payload
        )

        assert response.status_code == 401

    async def test_update_endpoint_updates_group_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test PUT /api/signal-chain-groups/{id} updates a group."""
        service = SignalChainGroupService(db_session)

        group = SignalChainGroup(
            user_id=test_user.id,
            name="Original",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [uuid4()]},
        )

        async with db_session.begin():
            await service.create(group)

        payload = {"name": "Updated"}

        response = await authenticated_client.put(
            f"/api/signal-chain-groups/{group.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"

    async def test_delete_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test DELETE /api/signal-chain-groups/{id} returns 401 without auth."""
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

        response = await unauthenticated_client.delete(f"/api/signal-chain-groups/{group.id}")

        assert response.status_code == 401

    async def test_delete_endpoint_deletes_group_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test DELETE /api/signal-chain-groups/{id} deletes a group."""
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

        response = await authenticated_client.delete(f"/api/signal-chain-groups/{group.id}")

        assert response.status_code == 204

        # Verify deletion
        retrieved = await service.get_by_id(group.id)
        assert retrieved is None

    async def test_generate_endpoint_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test POST /api/signal-chain-groups/{id}/generate returns 401 without auth."""
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

        response = await unauthenticated_client.post(
            f"/api/signal-chain-groups/{group.id}/generate"
        )

        assert response.status_code == 401

    async def test_generate_endpoint_generates_permutations_when_authenticated(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test POST /api/signal-chain-groups/{id}/generate generates permutations."""
        service = SignalChainGroupService(db_session)

        gear_id = uuid4()
        group = SignalChainGroup(
            user_id=test_user.id,
            name="Test Group",
            base_chain_id=base_chain.id,
            slot_positions=[0],
            gear_options={0: [gear_id]},
        )

        async with db_session.begin():
            await service.create(group)

        response = await authenticated_client.post(f"/api/signal-chain-groups/{group.id}/generate")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
