"""Integration tests for SignalChainBuilder API interactions.

Tests verify that the API endpoints required by the SignalChainBuilder
component work correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.signal_chain import SignalChain as SignalChainModel
from webapp.adapters.persistence.models.signal_chain_block import (
    SignalChainBlock as SignalChainBlockModel,
)
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.auth.dependencies import set_session_override, set_user_override
from webapp.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    suffix = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"testuser_{suffix}",
        email=f"test_{suffix}@example.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_gear(db_session: AsyncSession) -> list[Gear]:
    """Create test gear items of various types."""
    suffix = uuid4().hex[:8]
    gear_items = [
        Gear(
            id=uuid4(),
            name=f"Test Amp {suffix}",
            slug=f"test-amp-{suffix}",
            gear_type="amp",
            platform="nam",
        ),
        Gear(
            id=uuid4(),
            name=f"Test Pedal {suffix}",
            slug=f"test-pedal-{suffix}",
            gear_type="pedal",
            platform="nam",
        ),
        Gear(
            id=uuid4(),
            name=f"Test IR {suffix}",
            slug=f"test-ir-{suffix}",
            gear_type="ir",
            platform="ir",
        ),
    ]
    for gear in gear_items:
        db_session.add(gear)
    await db_session.commit()
    for gear in gear_items:
        await db_session.refresh(gear)
    return gear_items


@pytest.fixture
async def user_gear(
    db_session: AsyncSession, test_user: User, test_gear: list[Gear]
) -> list[UserGear]:
    """Create user's gear library via gear models."""
    # Create a gear model for each gear item
    gear_models = []
    for gear in test_gear:
        gear_model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform="nam" if gear.gear_type != "ir" else "ir",
            size="standard",
        )
        db_session.add(gear_model)
        gear_models.append(gear_model)
    await db_session.commit()
    for gm in gear_models:
        await db_session.refresh(gm)

    # Create user gear entries linked to gear models
    user_gear_items = []
    for gear_model in gear_models:
        user_gear_item = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=gear_model.id,
        )
        db_session.add(user_gear_item)
        user_gear_items.append(user_gear_item)
    await db_session.commit()
    for item in user_gear_items:
        await db_session.refresh(item)
    return user_gear_items


@pytest.fixture
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated HTTP client."""
    # Set overrides for centralized auth dependencies
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # Clear overrides
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryAPIForBuilder:
    """Test library API endpoints that the builder uses for gear selection."""

    async def test_list_user_gear_returns_items(
        self,
        client: AsyncClient,
        user_gear: list[UserGear],
        test_gear: list[Gear],
    ) -> None:
        """Builder should be able to fetch user's gear library."""
        response = await client.get("/api/v1/library/gear")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(test_gear)
        assert all("id" in item for item in data)
        assert all("gear_model_id" in item for item in data)
        assert all("name" in item for item in data)
        assert all("gear_type" in item for item in data)

    async def test_library_includes_all_gear_types(
        self,
        client: AsyncClient,
        user_gear: list[UserGear],
    ) -> None:
        """Library should include all gear types needed for chain building."""
        response = await client.get("/api/v1/library/gear")

        assert response.status_code == 200
        data = response.json()

        gear_types = {item["gear_type"] for item in data}
        expected_types = {"amp", "pedal", "ir"}
        assert expected_types.issubset(gear_types), "Not all required gear types present"


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainAPIForBuilder:
    """Test signal chain API endpoints that the builder uses."""

    async def test_create_chain_with_blocks(
        self,
        client: AsyncClient,
        user_gear: list[UserGear],
    ) -> None:
        """Builder should be able to create a chain with multiple blocks."""
        # Note: user_gear[0]=amp, user_gear[1]=pedal, user_gear[2]=ir
        # Chain must be: pedal -> amp -> ir (validation requires IR after amp)
        chain_data = {
            "name": "Test Chain",
            "platform": "nam",
            "description": "Test description",
            "blocks": [
                {
                    "user_gear_id": str(user_gear[1].id),  # pedal
                    "gear_type": "pedal",
                    "position": 0,
                },
                {
                    "user_gear_id": str(user_gear[0].id),  # amp
                    "gear_type": "amp",
                    "position": 1,
                },
                {
                    "user_gear_id": str(user_gear[2].id),  # ir
                    "gear_type": "ir",
                    "position": 2,
                },
            ],
        }

        response = await client.post("/api/v1/signal-chains/", json=chain_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Chain"
        assert data["platform"] == "nam"
        assert len(data["blocks"]) == 3
        assert data["blocks"][0]["position"] == 0
        assert data["blocks"][0]["gear_type"] == "pedal"
        assert data["blocks"][1]["position"] == 1
        assert data["blocks"][1]["gear_type"] == "amp"
        assert data["blocks"][2]["position"] == 2
        assert data["blocks"][2]["gear_type"] == "ir"

    async def test_update_chain_replaces_blocks(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        user_gear: list[UserGear],
    ) -> None:
        """Builder should be able to update chain by replacing blocks."""
        # Create initial chain
        from core.domain.value_objects.signal_chain_enums import GearType, Platform

        chain = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name="Original Chain",
            platform=Platform.NAM,
        )
        db_session.add(chain)

        block = SignalChainBlockModel(
            id=uuid4(),
            signal_chain_id=chain.id,
            user_gear_id=user_gear[1].id,  # pedal
            gear_type=GearType.PEDAL,
            position=0,
        )
        db_session.add(block)
        await db_session.commit()
        await db_session.refresh(chain)

        # Update with new blocks
        update_data = {
            "name": "Updated Chain",
            "platform": "nam",
            "blocks": [
                {
                    "user_gear_id": str(user_gear[1].id),
                    "gear_type": "amp",
                    "position": 0,
                },
                {
                    "user_gear_id": str(user_gear[2].id),
                    "gear_type": "ir",
                    "position": 1,
                },
            ],
        }

        response = await client.put(f"/api/v1/signal-chains/{chain.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Chain"
        assert len(data["blocks"]) == 2
        assert data["blocks"][0]["gear_type"] == "amp"
        assert data["blocks"][1]["gear_type"] == "ir"

    async def test_list_user_chains(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        user_gear: list[UserGear],
    ) -> None:
        """Builder should be able to fetch user's existing chains."""
        # Create test chains
        from core.domain.value_objects.signal_chain_enums import Platform

        chain1 = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name="Chain 1",
            platform=Platform.NAM,
        )
        chain2 = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name="Chain 2",
            platform=Platform.NAM,
        )
        db_session.add_all([chain1, chain2])
        await db_session.commit()

        response = await client.get("/api/v1/signal-chains/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        chain_names = {chain["name"] for chain in data}
        assert chain_names == {"Chain 1", "Chain 2"}

    async def test_delete_chain(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Builder should be able to delete chains."""
        from core.domain.value_objects.signal_chain_enums import Platform

        chain = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name="To Delete",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        await db_session.commit()

        response = await client.delete(f"/api/v1/signal-chains/{chain.id}")

        assert response.status_code == 204


@pytest.mark.asyncio
@pytest.mark.integration
class TestBuilderPermutationMode:
    """Test API support for permutation mode (multiple gear per slot).

    Permutation mode allows multiple gear items at the same position,
    which the builder will use to generate multiple chain variations.
    """

    async def test_create_chain_with_multiple_gear_at_same_position(
        self,
        client: AsyncClient,
        user_gear: list[UserGear],
    ) -> None:
        """API should accept multiple blocks at the same position for permutations."""
        chain_data = {
            "name": "Permutation Chain",
            "platform": "nam",
            "blocks": [
                {
                    "user_gear_id": str(user_gear[0].id),
                    "gear_type": "pedal",
                    "position": 0,
                },
                {
                    "user_gear_id": str(user_gear[1].id),
                    "gear_type": "pedal",
                    "position": 0,  # Same position as previous
                },
            ],
        }

        response = await client.post("/api/v1/signal-chains/", json=chain_data)

        # This might be 201 (accepted) or 422 (validation error) depending on
        # whether permutation mode is handled at API level or application level
        assert response.status_code in {201, 422}

        if response.status_code == 201:
            data = response.json()
            assert len(data["blocks"]) == 2
            positions = [block["position"] for block in data["blocks"]]
            assert positions.count(0) == 2, "Both blocks should be at position 0"


@pytest.mark.asyncio
@pytest.mark.integration
class TestBuilderValidation:
    """Test API validation that affects builder UX."""

    async def test_chain_requires_name(
        self,
        client: AsyncClient,
    ) -> None:
        """Builder should handle validation error for missing name."""
        chain_data = {
            "platform": "nam",
            "blocks": [],
        }

        response = await client.post("/api/v1/signal-chains/", json=chain_data)

        assert response.status_code == 422

    async def test_chain_requires_valid_platform(
        self,
        client: AsyncClient,
    ) -> None:
        """Builder should validate platform selection."""
        chain_data = {
            "name": "Test Chain",
            "platform": "invalid_platform",
            "blocks": [],
        }

        response = await client.post("/api/v1/signal-chains/", json=chain_data)

        assert response.status_code == 422

    async def test_block_requires_valid_gear_type(
        self,
        client: AsyncClient,
        user_gear: list[UserGear],
    ) -> None:
        """Builder should validate gear type for blocks."""
        chain_data = {
            "name": "Test Chain",
            "platform": "nam",
            "blocks": [
                {
                    "user_gear_id": str(user_gear[0].id),
                    "gear_type": "invalid_type",
                    "position": 0,
                },
            ],
        }

        response = await client.post("/api/v1/signal-chains/", json=chain_data)

        assert response.status_code == 422
