"""Integration tests for shootout creation wizard with group-based chain selection.

Tests T98: Wizard Chain Selection from Groups
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.signal_chain_group import SignalChainGroup
from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain as SignalChainModel,
)
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.html import router
from webapp.services.signal_chain_group_service import SignalChainGroupService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with html router."""
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
async def base_chain(db_session: AsyncSession, test_user: User) -> SignalChainModel:
    """Create a base signal chain for group generation."""
    chain = SignalChainModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Base Chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def group_with_generated_chains(
    db_session: AsyncSession,
    test_user: User,
    base_chain: SignalChainModel,
) -> tuple[SignalChainGroup, list[str]]:
    """Create a group and generate chains from it."""
    # Create group with 2x2 permutations (4 chains)
    group = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Group",
        description="Test group for wizard",
        base_chain_id=base_chain.id,
        slot_positions=[0, 1],
        gear_options={
            0: [uuid4(), uuid4()],  # 2 options at position 0
            1: [uuid4(), uuid4()],  # 2 options at position 1
        },
        include_null=False,
    )

    # Save group and generate chains
    service = SignalChainGroupService(db_session)
    async with db_session.begin():
        await service.create(group)
        chain_ids = await service.generate_permutations(group.id)

    return group, chain_ids


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    from webapp.auth.dependencies import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_chains_endpoint_returns_generated_chains(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    group_with_generated_chains: tuple[SignalChainGroup, list[str]],
) -> None:
    """Test GET /api/v1/html/shootout-create/group-chains/{group_id} returns chains."""
    group, chain_ids = group_with_generated_chains

    response = await authenticated_client.get(
        f"/api/v1/html/shootout-create/group-chains/{group.id}"
    )

    assert response.status_code == 200
    html = response.text

    # Verify HTML contains chain references
    assert "Test Group" in html or len(chain_ids) > 0
    for chain_id in chain_ids:
        # Check if chain ID appears in HTML (as checkbox value or data attribute)
        assert chain_id in html


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_chains_endpoint_returns_404_for_nonexistent_group(
    authenticated_client: AsyncClient,
) -> None:
    """Test GET /api/v1/html/shootout-create/group-chains/{group_id} returns 404 for missing group."""
    fake_group_id = uuid4()

    response = await authenticated_client.get(
        f"/api/v1/html/shootout-create/group-chains/{fake_group_id}"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_chains_endpoint_returns_404_for_other_users_group(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test GET /api/v1/html/shootout-create/group-chains/{group_id} returns 404 for other user's group."""
    # Create another user and their group
    other_user = User(username="other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_chain = SignalChainModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other Chain",
        platform=Platform.NAM,
    )
    db_session.add(other_chain)
    await db_session.flush()

    other_group = SignalChainGroup(
        id=uuid4(),
        user_id=other_user.id,
        name="Other Group",
        base_chain_id=other_chain.id,
        slot_positions=[0],
        gear_options={0: [uuid4()]},
    )

    service = SignalChainGroupService(db_session)
    async with db_session.begin():
        await service.create(other_group)

    # Try to access other user's group
    response = await authenticated_client.get(
        f"/api/v1/html/shootout-create/group-chains/{other_group.id}"
    )

    # Returns 404 to avoid leaking existence
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_chains_endpoint_only_returns_chains_from_specified_group(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test endpoint only returns chains from the specified group."""
    # Create two groups with different chain counts
    base_chain1 = SignalChainModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Base Chain 1",
        platform=Platform.NAM,
    )
    base_chain2 = SignalChainModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Base Chain 2",
        platform=Platform.NAM,
    )
    db_session.add_all([base_chain1, base_chain2])
    await db_session.flush()

    group1 = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Group Alpha",
        base_chain_id=base_chain1.id,
        slot_positions=[0],
        gear_options={0: [uuid4(), uuid4()]},  # 2 chains
    )

    group2 = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Group Beta",
        base_chain_id=base_chain2.id,
        slot_positions=[0],
        gear_options={0: [uuid4(), uuid4(), uuid4()]},  # 3 chains
    )

    service = SignalChainGroupService(db_session)
    async with db_session.begin():
        await service.create(group1)
        await service.create(group2)
        chain_ids_1 = await service.generate_permutations(group1.id)
        chain_ids_2 = await service.generate_permutations(group2.id)

    # Request group1's chains
    response = await authenticated_client.get(
        f"/api/v1/html/shootout-create/group-chains/{group1.id}"
    )

    assert response.status_code == 200
    html = response.text

    # Verify only group1's chains are present
    for chain_id in chain_ids_1:
        assert chain_id in html

    # Verify group2's chains are NOT present
    for chain_id in chain_ids_2:
        assert chain_id not in html


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_chains_endpoint_returns_empty_when_no_chains_generated(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test endpoint returns valid HTML when group has no generated chains yet."""
    base_chain = SignalChainModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Base Chain",
        platform=Platform.NAM,
    )
    db_session.add(base_chain)
    await db_session.flush()

    # Create group but don't generate chains
    group = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Empty Group",
        base_chain_id=base_chain.id,
        slot_positions=[0],
        gear_options={0: [uuid4()]},
    )

    service = SignalChainGroupService(db_session)
    async with db_session.begin():
        await service.create(group)
        # Note: NOT calling generate_permutations

    response = await authenticated_client.get(
        f"/api/v1/html/shootout-create/group-chains/{group.id}"
    )

    assert response.status_code == 200
    html = response.text

    # Should return valid HTML (empty state or message)
    assert len(html) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_create_with_group_chains_persists_selection(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    group_with_generated_chains: tuple[SignalChainGroup, list[str]],
) -> None:
    """Test creating shootout with chains selected from groups persists correctly."""
    from webapp.adapters.persistence.models.di_track import DITrack

    # Create a DI track for the shootout
    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI",
        file_path="/path/to/di.wav",
        original_filename="di.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()

    _group, chain_ids = group_with_generated_chains

    # Select 2 chains from the generated group chains
    selected_chain_ids = chain_ids[:2]

    # Submit wizard form with group-based chain selection
    form_data = {
        "name": "Shootout from Groups",
        "di_track_id": str(di_track.id),
        "chain_ids[]": selected_chain_ids,
    }

    response = await authenticated_client.post(
        "/api/v1/html/shootout-create",
        data=form_data,
    )

    # Should redirect to shootout detail page
    assert response.status_code == 200
    assert "HX-Redirect" in response.headers

    # Verify shootout was created with selected chains
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from webapp.adapters.persistence.models.shootout import Shootout

    stmt = (
        select(Shootout)
        .where(Shootout.user_id == test_user.id)
        .where(Shootout.name == "Shootout from Groups")
        .options(joinedload(Shootout.chains))
    )
    result = await db_session.execute(stmt)
    shootout = result.unique().scalar_one_or_none()

    assert shootout is not None
    assert len(shootout.chains) == 2

    # Verify the chains are from our group
    shootout_chain_ids = {str(sc.signal_chain_id) for sc in shootout.chains}
    assert shootout_chain_ids == set(selected_chain_ids)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_create_validates_minimum_two_chains(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    group_with_generated_chains: tuple[SignalChainGroup, list[str]],
) -> None:
    """Test shootout creation enforces minimum 2 chains validation."""
    from webapp.adapters.persistence.models.di_track import DITrack

    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI",
        file_path="/path/to/di.wav",
        original_filename="di.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()

    _group, chain_ids = group_with_generated_chains

    # Try to submit with only 1 chain
    form_data = {
        "name": "Invalid Shootout",
        "di_track_id": str(di_track.id),
        "chain_ids[]": [chain_ids[0]],  # Only 1 chain
    }

    response = await authenticated_client.post(
        "/api/v1/html/shootout-create",
        data=form_data,
    )

    # Should fail validation (either 400 or 422)
    assert response.status_code in [400, 422]
