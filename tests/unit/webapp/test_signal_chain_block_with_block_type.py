"""Unit tests for SignalChainBlock with BlockType reference."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.signal_chain import (
    BlockType,
    SignalChain,
    SignalChainBlock,
)
from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_signal_chain_block_with_block_type_id(session: AsyncSession) -> None:
    """Test that SignalChainBlock can reference a BlockType instead of user gear."""
    # Arrange - Create user, chain, and block type
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block_type = BlockType(
        name="Compressor",
        category="dynamics",
        default_params={"ratio": 4.0},
    )
    session.add(block_type)
    await session.commit()

    # Act - Create block with block_type_id (no user_gear_id)
    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        block_type_id=block_type.id,
    )
    session.add(block)
    await session.commit()

    # Assert
    assert block.id is not None
    assert block.block_type_id == block_type.id
    assert block.user_gear_id is None  # Should be nullable when block_type_id is set


@pytest.mark.asyncio
async def test_signal_chain_block_has_block_type_id_field(session: AsyncSession) -> None:
    """Test that SignalChainBlock model has block_type_id field."""
    # This test verifies the field exists on the model
    assert hasattr(SignalChainBlock, "block_type_id")


@pytest.mark.asyncio
async def test_signal_chain_block_user_gear_id_nullable(session: AsyncSession) -> None:
    """Test that user_gear_id can be NULL when block_type_id is set."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block_type = BlockType(
        name="EQ",
        category="eq",
        default_params={},
    )
    session.add(block_type)
    await session.commit()

    # Create block with ONLY block_type_id
    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        block_type_id=block_type.id,
        user_gear_id=None,  # Should be allowed to be None
    )
    session.add(block)
    await session.commit()

    assert block.user_gear_id is None
    assert block.block_type_id is not None


@pytest.mark.asyncio
async def test_signal_chain_block_has_block_type_relationship(session: AsyncSession) -> None:
    """Test that SignalChainBlock has relationship to BlockType."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block_type = BlockType(
        name="Reverb",
        category="modulation",
        default_params={"mix": 0.3},
    )
    session.add(block_type)
    await session.commit()

    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        block_type_id=block_type.id,
    )
    session.add(block)
    await session.commit()

    # Re-query with joinedload to eagerly load relationship (lazy="raise" on model)
    result = await session.execute(
        select(SignalChainBlock)
        .where(SignalChainBlock.id == block.id)
        .options(joinedload(SignalChainBlock.block_type))
    )
    block = result.unique().scalar_one()

    # Assert - Check relationship exists
    assert hasattr(block, "block_type")
    assert block.block_type is not None
    assert block.block_type.name == "Reverb"


@pytest.mark.asyncio
async def test_signal_chain_block_gear_type_nullable(session: AsyncSession) -> None:
    """Test that gear_type is nullable when using BlockType."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    block_type = BlockType(
        name="Delay",
        category="modulation",
        default_params={},
    )
    session.add(block_type)
    await session.commit()

    # Create block with BlockType - gear_type should be nullable
    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        block_type_id=block_type.id,
        gear_type=None,  # Should be nullable when using BlockType
    )
    session.add(block)
    await session.commit()

    assert block.gear_type is None
    assert block.block_type_id is not None
