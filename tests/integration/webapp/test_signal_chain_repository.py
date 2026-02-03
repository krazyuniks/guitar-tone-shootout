"""Integration tests for SignalChainRepository."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.signal_chain import SignalChain, SignalChainBlock
from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)

if TYPE_CHECKING:
    from datetime import datetime


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
def sample_chain(test_user: User) -> SignalChain:
    """Create a sample signal chain entity."""
    chain = SignalChain(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Chain",
        description="A test signal chain",
        platform=Platform.NAM,
    )
    return chain


@pytest.fixture
def sample_block(sample_chain: SignalChain) -> SignalChainBlock:
    """Create a sample block entity."""
    return SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=0,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.AMP,
    )


async def test_save_new_chain(
    session: AsyncSession,
    sample_chain: SignalChain,
    sample_block: SignalChainBlock,
) -> None:
    """Test saving a new signal chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Add block to chain
    sample_chain.blocks.append(sample_block)

    # Save the chain
    await repo.save(sample_chain)
    await session.commit()

    # Verify it was saved
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is not None
    assert retrieved.id == sample_chain.id
    assert retrieved.name == "Test Chain"
    assert retrieved.description == "A test signal chain"
    assert retrieved.platform == Platform.NAM
    assert len(retrieved.blocks) == 1
    assert retrieved.blocks[0].id == sample_block.id
    assert retrieved.blocks[0].position == 0
    assert retrieved.blocks[0].gear_type == GearType.AMP


async def test_save_update_chain(
    session: AsyncSession,
    sample_chain: SignalChain,
) -> None:
    """Test updating an existing signal chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Save initial chain
    await repo.save(sample_chain)
    await session.commit()

    # Update the chain
    updated_chain = SignalChain(
        id=sample_chain.id,
        user_id=sample_chain.user_id,
        name="Updated Chain",
        description="Updated description",
        platform=Platform.NAM,
        created_at=sample_chain.created_at,
        updated_at=sample_chain.updated_at,
    )
    await repo.save(updated_chain)
    await session.commit()

    # Expire all objects to force a fresh load from DB
    session.expire_all()

    # Verify the update
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is not None
    assert retrieved.name == "Updated Chain"
    assert retrieved.description == "Updated description"


async def test_save_with_multiple_blocks(
    session: AsyncSession,
    sample_chain: SignalChain,
) -> None:
    """Test saving a chain with multiple blocks."""
    repo = SQLAlchemySignalChainRepository(session)

    # Add multiple blocks
    block1 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=0,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.PEDAL,
    )
    block2 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=1,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.AMP,
    )
    block3 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=2,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.IR,
    )
    sample_chain.blocks.extend([block1, block2, block3])

    # Save the chain
    await repo.save(sample_chain)
    await session.commit()

    # Verify all blocks were saved
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is not None
    assert len(retrieved.blocks) == 3
    assert retrieved.blocks[0].position == 0
    assert retrieved.blocks[0].gear_type == GearType.PEDAL
    assert retrieved.blocks[1].position == 1
    assert retrieved.blocks[1].gear_type == GearType.AMP
    assert retrieved.blocks[2].position == 2
    assert retrieved.blocks[2].gear_type == GearType.IR


async def test_update_blocks(
    session: AsyncSession,
    sample_chain: SignalChain,
) -> None:
    """Test updating blocks in a chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Save chain with initial blocks
    block1 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=0,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.PEDAL,
    )
    block2 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=1,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.AMP,
    )
    sample_chain.blocks.extend([block1, block2])
    await repo.save(sample_chain)
    await session.commit()

    # Update chain with modified blocks
    updated_chain = SignalChain(
        id=sample_chain.id,
        user_id=sample_chain.user_id,
        name=sample_chain.name,
        platform=sample_chain.platform,
        created_at=sample_chain.created_at,
        updated_at=sample_chain.updated_at,
    )
    # Keep block1, remove block2, add new block3
    new_block = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=1,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.IR,
    )
    updated_chain.blocks.extend([block1, new_block])
    await repo.save(updated_chain)
    await session.commit()

    # Expire all objects to force a fresh load from DB
    session.expire_all()

    # Verify blocks were updated
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is not None
    assert len(retrieved.blocks) == 2
    assert retrieved.blocks[0].id == block1.id
    assert retrieved.blocks[1].id == new_block.id
    assert retrieved.blocks[1].gear_type == GearType.IR


async def test_get_by_user_id(
    session: AsyncSession,
    test_user: User,
) -> None:
    """Test getting chains by user_id."""
    repo = SQLAlchemySignalChainRepository(session)

    # Create multiple chains
    chain1 = SignalChain(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Chain 1",
        platform=Platform.NAM,
    )
    chain2 = SignalChain(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Chain 2",
        platform=Platform.NAM,
    )
    chain3 = SignalChain(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),  # Different user
        name="Chain 3",
        platform=Platform.NAM,
    )

    await repo.save(chain1)
    await repo.save(chain2)
    await repo.save(chain3)
    await session.commit()

    # Get chains for test_user
    chains = await repo.get_by_user_id(test_user.id)
    assert len(chains) == 2
    assert {chain.id for chain in chains} == {chain1.id, chain2.id}


async def test_get_by_user_id_pagination(
    session: AsyncSession,
    test_user: User,
) -> None:
    """Test pagination for get_by_user_id."""
    repo = SQLAlchemySignalChainRepository(session)

    # Create 5 chains
    for i in range(5):
        chain = SignalChain(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name=f"Chain {i}",
            platform=Platform.NAM,
        )
        await repo.save(chain)
    await session.commit()

    # Get first 2 chains
    chains = await repo.get_by_user_id(test_user.id, limit=2, offset=0)
    assert len(chains) == 2

    # Get next 2 chains
    chains = await repo.get_by_user_id(test_user.id, limit=2, offset=2)
    assert len(chains) == 2


async def test_count_by_user_id(
    session: AsyncSession,
    test_user: User,
) -> None:
    """Test counting chains by user_id."""
    repo = SQLAlchemySignalChainRepository(session)

    # Create multiple chains
    for i in range(3):
        chain = SignalChain(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name=f"Chain {i}",
            platform=Platform.NAM,
        )
        await repo.save(chain)
    await session.commit()

    # Count chains
    count = await repo.count_by_user_id(test_user.id)
    assert count == 3


async def test_delete_chain(
    session: AsyncSession,
    sample_chain: SignalChain,
    sample_block: SignalChainBlock,
) -> None:
    """Test deleting a signal chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Save chain with blocks
    sample_chain.blocks.append(sample_block)
    await repo.save(sample_chain)
    await session.commit()

    # Delete the chain
    await repo.delete(sample_chain.id)
    await session.commit()

    # Verify it was deleted
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is None


async def test_delete_nonexistent_chain(session: AsyncSession) -> None:
    """Test deleting a nonexistent chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Delete nonexistent chain (should not raise error)
    await repo.delete(uuid.uuid4())
    await session.commit()


async def test_get_nonexistent_chain(session: AsyncSession) -> None:
    """Test getting a nonexistent chain."""
    repo = SQLAlchemySignalChainRepository(session)

    # Get nonexistent chain
    retrieved = await repo.get_by_id(uuid.uuid4())
    assert retrieved is None


async def test_blocks_sorted_by_position(
    session: AsyncSession,
    sample_chain: SignalChain,
) -> None:
    """Test that blocks are always returned sorted by position."""
    repo = SQLAlchemySignalChainRepository(session)

    # Add blocks in random order
    block1 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=2,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.IR,
    )
    block2 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=0,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.PEDAL,
    )
    block3 = SignalChainBlock(
        id=uuid.uuid4(),
        signal_chain_id=sample_chain.id,
        position=1,
        user_gear_id=uuid.uuid4(),
        gear_type=GearType.AMP,
    )
    sample_chain.blocks.extend([block1, block2, block3])

    # Save the chain
    await repo.save(sample_chain)
    await session.commit()

    # Verify blocks are sorted by position
    retrieved = await repo.get_by_id(sample_chain.id)
    assert retrieved is not None
    assert len(retrieved.blocks) == 3
    assert retrieved.blocks[0].position == 0
    assert retrieved.blocks[1].position == 1
    assert retrieved.blocks[2].position == 2
