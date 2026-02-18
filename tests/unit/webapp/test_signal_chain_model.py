"""Unit tests for SignalChain ORM models."""

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.block_type import BlockType
from webapp.adapters.persistence.models.preset import Preset
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainBlock,
    SignalChainGroup,
)
from webapp.adapters.persistence.models.user import User


async def test_signal_chain_creation(session: AsyncSession) -> None:
    """Test creating a signal chain with basic fields."""
    # Arrange - Create user
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    # Act - Create signal chain
    chain = SignalChain(
        user_id=user.id,
        name="My Chain",
        description="A test chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    # Assert
    assert chain.id is not None
    assert isinstance(chain.id, UUID)
    assert chain.user_id == user.id
    assert chain.name == "My Chain"
    assert chain.description == "A test chain"
    assert chain.platform == Platform.NAM
    assert chain.created_at is not None
    assert chain.updated_at is not None


async def test_signal_chain_blocks(session: AsyncSession) -> None:
    """Test signal chain with blocks."""
    # Arrange - Create user and chain
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Chain with blocks",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    # Create blocks
    block1 = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=UUID("00000000-0000-0000-0000-000000000001"),
        gear_type=GearType.PEDAL,
    )
    block2 = SignalChainBlock(
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=UUID("00000000-0000-0000-0000-000000000002"),
        gear_type=GearType.AMP,
    )
    session.add_all([block1, block2])
    await session.commit()

    # Re-query with joinedload to eagerly load blocks (lazy="raise" on model)
    result = await session.execute(
        select(SignalChain)
        .where(SignalChain.id == chain.id)
        .options(joinedload(SignalChain.blocks))
    )
    chain = result.unique().scalar_one()

    # Assert
    assert len(chain.blocks) == 2
    assert chain.blocks[0].position == 0
    assert chain.blocks[0].gear_type == GearType.PEDAL
    assert chain.blocks[1].position == 1
    assert chain.blocks[1].gear_type == GearType.AMP


async def test_signal_chain_cascade_delete(session: AsyncSession) -> None:
    """Test that deleting chain cascades to blocks."""
    # Arrange
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Chain to delete",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=UUID("00000000-0000-0000-0000-000000000001"),
        gear_type=GearType.AMP,
    )
    session.add(block)
    await session.commit()

    # Act - Delete chain
    await session.delete(chain)
    await session.commit()

    # Assert - Block should be deleted
    result = await session.get(SignalChainBlock, block.id)
    assert result is None


async def test_block_type_creation(session: AsyncSession) -> None:
    """Test creating built-in processor definitions."""
    suffix = uuid.uuid4().hex[:8]
    # Arrange & Act
    block_type = BlockType(
        name=f"Compressor_{suffix}",
        category="dynamics",
        description="Audio compressor",
        default_params={"ratio": 4.0, "threshold": -20.0},
    )
    session.add(block_type)
    await session.commit()

    # Assert
    assert block_type.id is not None
    assert block_type.name == f"Compressor_{suffix}"
    assert block_type.category == "dynamics"
    assert block_type.default_params["ratio"] == 4.0


async def test_preset_creation(session: AsyncSession) -> None:
    """Test creating parameter presets for blocks."""
    suffix = uuid.uuid4().hex[:8]
    # Arrange - Create block type and chain
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=UUID("00000000-0000-0000-0000-000000000001"),
        gear_type=GearType.PEDAL,
    )
    session.add(block)
    await session.commit()

    # Act - Create preset
    preset = Preset(
        signal_chain_block_id=block.id,
        name=f"Heavy Compression {suffix}",
        params={"ratio": 8.0, "threshold": -30.0, "attack": 5.0},
    )
    session.add(preset)
    await session.commit()

    # Assert
    assert preset.id is not None
    assert preset.signal_chain_block_id == block.id
    assert preset.name == f"Heavy Compression {suffix}"
    assert preset.params["ratio"] == 8.0


async def test_signal_chain_group_creation(session: AsyncSession) -> None:
    """Test creating signal chain group for permutations."""
    # Arrange - Create user and base chain
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    base_chain = SignalChain(
        user_id=user.id,
        name="Base Chain",
        platform=Platform.NAM,
    )
    session.add(base_chain)
    await session.commit()

    # Act - Create group
    group = SignalChainGroup(
        user_id=user.id,
        name="Amp Comparison",
        description="Compare 3 amps",
        base_chain_id=base_chain.id,
        slot_positions=[1],
        gear_options={
            1: ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"]
        },
        include_null=False,
    )
    session.add(group)
    await session.commit()

    # Assert
    assert group.id is not None
    assert group.user_id == user.id
    assert group.base_chain_id == base_chain.id
    assert group.slot_positions == [1]
    assert len(group.gear_options[1]) == 2


async def test_signal_chain_user_relationship(session: AsyncSession) -> None:
    """Test relationship between signal chain and user."""
    # Arrange
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
    )
    session.add(user)
    await session.commit()

    chain1 = SignalChain(
        user_id=user.id,
        name="Chain 1",
        platform=Platform.NAM,
    )
    chain2 = SignalChain(
        user_id=user.id,
        name="Chain 2",
        platform=Platform.AIDA_X,
    )
    session.add_all([chain1, chain2])
    await session.commit()

    # Query to get chains for user
    result = await session.execute(
        select(SignalChain).where(SignalChain.user_id == user.id).order_by(SignalChain.name)
    )
    chains = list(result.scalars().all())

    # Assert
    assert len(chains) == 2
    assert chains[0].name == "Chain 1"
    assert chains[1].name == "Chain 2"
    assert chains[0].user_id == user.id
    assert chains[1].user_id == user.id
