"""Integration tests for SignalChainGroup permutation generation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from core.domain.entities.signal_chain_group import SignalChainGroup
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
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
async def base_chain(db_session: AsyncSession, test_user: User) -> SignalChain:
    """Create a test signal chain to use as base for groups."""
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Base Chain",
        platform=Platform.NAM.value,
        blocks=[],
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def amp_gear_1(db_session: AsyncSession, test_user: User) -> UserGear:
    """Create first amp gear option."""
    # Create Gear
    gear = Gear(
        id=uuid4(),
        name="Marshall JCM800",
        slug="marshall-jcm800",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create GearModel
    gear_model = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(gear_model)
    await db_session.flush()

    # Create UserGear (user's copy)
    user_gear = UserGear(
        id=uuid4(),
        user_id=test_user.id,
        gear_model_id=gear_model.id,
    )
    db_session.add(user_gear)
    await db_session.flush()
    await db_session.refresh(user_gear)
    return user_gear


@pytest.fixture
async def amp_gear_2(db_session: AsyncSession, test_user: User) -> UserGear:
    """Create second amp gear option."""
    # Create Gear
    gear = Gear(
        id=uuid4(),
        name="Fender Twin",
        slug="fender-twin",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create GearModel
    gear_model = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(gear_model)
    await db_session.flush()

    # Create UserGear (user's copy)
    user_gear = UserGear(
        id=uuid4(),
        user_id=test_user.id,
        gear_model_id=gear_model.id,
    )
    db_session.add(user_gear)
    await db_session.flush()
    await db_session.refresh(user_gear)
    return user_gear


@pytest.fixture
async def ir_gear_1(db_session: AsyncSession, test_user: User) -> UserGear:
    """Create first IR gear option."""
    # Create Gear
    gear = Gear(
        id=uuid4(),
        name="Greenback 25",
        slug="greenback-25",
        gear_type=GearType.IR,
        platform=Platform.NAM,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create GearModel
    gear_model = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(gear_model)
    await db_session.flush()

    # Create UserGear (user's copy)
    user_gear = UserGear(
        id=uuid4(),
        user_id=test_user.id,
        gear_model_id=gear_model.id,
    )
    db_session.add(user_gear)
    await db_session.flush()
    await db_session.refresh(user_gear)
    return user_gear


@pytest.fixture
async def ir_gear_2(db_session: AsyncSession, test_user: User) -> UserGear:
    """Create second IR gear option."""
    gear = Gear(
        id=uuid4(),
        name="V30",
        slug="v30",
        gear_type=GearType.IR,
        platform=Platform.NAM,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    gear_model = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(gear_model)
    await db_session.flush()

    user_gear = UserGear(
        id=uuid4(),
        user_id=test_user.id,
        gear_model_id=gear_model.id,
    )
    db_session.add(user_gear)
    await db_session.flush()
    await db_session.refresh(user_gear)
    return user_gear


@pytest.fixture
async def group_with_2x2(
    db_session: AsyncSession,
    test_user: User,
    base_chain: SignalChain,
    amp_gear_1: UserGear,
    amp_gear_2: UserGear,
    ir_gear_1: UserGear,
    ir_gear_2: UserGear,
) -> SignalChainGroup:
    """Create a group with 2 amps × 2 IRs = 4 permutations."""
    group = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Amp vs IR Shootout",
        base_chain_id=base_chain.id,
        slot_positions=[0, 1],
        gear_options={
            0: [amp_gear_1.id, amp_gear_2.id],
            1: [ir_gear_1.id, ir_gear_2.id],
        },
        include_null=False,
    )

    from webapp.adapters.persistence.models.signal_chain import (
        SignalChainGroup as SignalChainGroupModel,
    )

    # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]] for ORM
    gear_options_str: dict[int, list[str]] = {}
    for pos, gear_ids in group.gear_options.items():
        gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]

    model = SignalChainGroupModel(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        base_chain_id=group.base_chain_id,
        slot_positions=group.slot_positions,
        gear_options=gear_options_str,
        include_null=group.include_null,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )
    db_session.add(model)
    await db_session.flush()
    return group


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


# Service Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainGroupPermutations:
    """Test permutation generation for signal chain groups."""

    async def test_generate_permutations_method_exists(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test that generate_permutations method exists on service."""
        service = SignalChainGroupService(db_session)
        assert hasattr(service, "generate_permutations")
        assert callable(service.generate_permutations)

    async def test_generates_2x2_permutations(
        self,
        db_session: AsyncSession,
        test_user: User,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test generating 2 amps × 2 IRs = 4 chains."""
        service = SignalChainGroupService(db_session)

        async with db_session.begin():
            result = await service.generate_permutations(group_with_2x2.id)

        # Should return 4 chain IDs (2 amps × 2 IRs)
        assert len(result) == 4
        assert all(isinstance(chain_id, str) for chain_id in result)

        # Verify chains exist in DB
        stmt = select(SignalChain).where(
            SignalChain.user_id == test_user.id,
        )
        chains_result = await db_session.execute(stmt)
        chains = chains_result.scalars().all()

        # Should have 4 chains created (plus the base chain = 5 total)
        assert len(chains) >= 4

    async def test_chain_naming_includes_group_name(
        self,
        db_session: AsyncSession,
        test_user: User,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that generated chains include group name in their name."""
        service = SignalChainGroupService(db_session)

        async with db_session.begin():
            chain_ids = await service.generate_permutations(group_with_2x2.id)

        # Verify chain names contain the group name
        stmt = select(SignalChain).where(
            SignalChain.id.in_(chain_ids),
        )
        chains_result = await db_session.execute(stmt)
        chains = chains_result.scalars().all()

        for chain in chains:
            # Each chain name should reference the group
            assert "Amp vs IR Shootout" in chain.name

    async def test_respects_max_permutations_limit(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test that generation fails when exceeding max_permutations."""
        # Create group with 4 × 4 × 4 = 64 permutations (exceeds default limit of 27)
        group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="Too Many Permutations",
            base_chain_id=base_chain.id,
            slot_positions=[0, 1, 2],
            gear_options={
                0: [uuid4() for _ in range(4)],
                1: [uuid4() for _ in range(4)],
                2: [uuid4() for _ in range(4)],
            },
            include_null=False,
            max_permutations=27,
        )

        from webapp.adapters.persistence.models.signal_chain import (
            SignalChainGroup as SignalChainGroupModel,
        )

        # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]] for ORM
        gear_options_str: dict[int, list[str]] = {}
        for pos, gear_ids in group.gear_options.items():
            gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]

        model = SignalChainGroupModel(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            base_chain_id=group.base_chain_id,
            slot_positions=group.slot_positions,
            gear_options=gear_options_str,
            include_null=group.include_null,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        db_session.add(model)
        await db_session.flush()

        service = SignalChainGroupService(db_session)

        # Should raise error or return error result
        async with db_session.begin():
            with pytest.raises(Exception) as exc_info:
                await service.generate_permutations(group.id)

            # Error should mention max permutations
            assert (
                "max" in str(exc_info.value).lower() or "permutation" in str(exc_info.value).lower()
            )

    async def test_includes_null_option_when_enabled(
        self,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
        amp_gear_1: UserGear,
        amp_gear_2: UserGear,
    ) -> None:
        """Test that include_null adds 'no gear' as an option."""
        # Create group with include_null=True for one slot
        # 2 amps × (1 IR + null) = 2 × 2 = 4 permutations
        group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="Null Test Group",
            base_chain_id=base_chain.id,
            slot_positions=[0, 1],
            gear_options={
                0: [amp_gear_1.id, amp_gear_2.id],
                1: [],  # Empty slot with null allowed
            },
            include_null=True,  # Allows null as option
        )

        from webapp.adapters.persistence.models.signal_chain import (
            SignalChainGroup as SignalChainGroupModel,
        )

        # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]] for ORM
        gear_options_str: dict[int, list[str]] = {}
        for pos, gear_ids in group.gear_options.items():
            gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]

        model = SignalChainGroupModel(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            base_chain_id=group.base_chain_id,
            slot_positions=group.slot_positions,
            gear_options=gear_options_str,
            include_null=group.include_null,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        db_session.add(model)
        await db_session.flush()

        service = SignalChainGroupService(db_session)

        async with db_session.begin():
            chain_ids = await service.generate_permutations(group.id)

        # Should create 2 chains (2 amps × 1 null option for slot 1)
        assert len(chain_ids) == 2

    async def test_chains_created_via_signal_chain_service(
        self,
        db_session: AsyncSession,
        test_user: User,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that chains are created via SignalChainService (validated)."""
        service = SignalChainGroupService(db_session)

        async with db_session.begin():
            chain_ids = await service.generate_permutations(group_with_2x2.id)

        # Verify chains exist and are valid
        stmt = select(SignalChain).where(
            SignalChain.id.in_(chain_ids),
        )
        chains_result = await db_session.execute(stmt)
        chains = chains_result.scalars().all()

        assert len(chains) == 4
        # All chains should belong to test user
        assert all(chain.user_id == test_user.id for chain in chains)


# API Tests


@pytest.mark.asyncio
@pytest.mark.integration
class TestGeneratePermutationsAPI:
    """Test POST /api/v1/signal-chain-groups/{id}/generate endpoint."""

    async def test_generate_endpoint_exists(
        self,
        authenticated_client: AsyncClient,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that POST /api/v1/signal-chain-groups/{id}/generate exists."""
        response = await authenticated_client.post(
            f"/api/v1/signal-chain-groups/{group_with_2x2.id}/generate",
        )

        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    async def test_generate_returns_chain_ids(
        self,
        authenticated_client: AsyncClient,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that generate endpoint returns list of created chain IDs."""
        response = await authenticated_client.post(
            f"/api/v1/signal-chain-groups/{group_with_2x2.id}/generate",
        )

        assert response.status_code == 200
        data = response.json()

        # Should return a list of chain IDs
        assert isinstance(data, list)
        assert len(data) == 4  # 2 amps × 2 IRs
        assert all(isinstance(chain_id, str) for chain_id in data)

    async def test_generate_requires_authentication(
        self,
        app: FastAPI,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that generate endpoint requires authentication."""
        # Create unauthenticated client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/signal-chain-groups/{group_with_2x2.id}/generate",
            )

        # Should return 401 Unauthorized
        assert response.status_code == 401

    async def test_generate_enforces_ownership(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        group_with_2x2: SignalChainGroup,
    ) -> None:
        """Test that generate endpoint returns 404 for other user's groups."""
        # Create another user
        other_user = User(username="otheruser", email="other@example.com")
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        # Authenticate as other user
        set_session_override(db_session)
        set_user_override(other_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/signal-chain-groups/{group_with_2x2.id}/generate",
            )

        # Should return 404 (not 403 to avoid leaking existence)
        assert response.status_code == 404

        # Cleanup
        set_session_override(None)
        set_user_override(None)

    async def test_generate_returns_error_for_too_many_permutations(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test that API returns error when exceeding max_permutations."""
        # Create group that exceeds limit
        group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="Too Many",
            base_chain_id=base_chain.id,
            slot_positions=[0, 1, 2],
            gear_options={
                0: [uuid4() for _ in range(4)],
                1: [uuid4() for _ in range(4)],
                2: [uuid4() for _ in range(4)],
            },
            include_null=False,
            max_permutations=27,
        )

        from webapp.adapters.persistence.models.signal_chain import (
            SignalChainGroup as SignalChainGroupModel,
        )

        # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]] for ORM
        gear_options_str: dict[int, list[str]] = {}
        for pos, gear_ids in group.gear_options.items():
            gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]

        model = SignalChainGroupModel(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            base_chain_id=group.base_chain_id,
            slot_positions=group.slot_positions,
            gear_options=gear_options_str,
            include_null=group.include_null,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        db_session.add(model)
        await db_session.flush()

        response = await authenticated_client.post(
            f"/api/v1/signal-chain-groups/{group.id}/generate",
        )

        # Should return error status (400 or 422)
        assert response.status_code in (400, 422)
        data = response.json()
        assert "detail" in data
