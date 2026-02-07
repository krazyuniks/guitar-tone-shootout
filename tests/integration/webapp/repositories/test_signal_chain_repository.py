"""Integration tests for SignalChainRepository joinedload conversion (T39).

Tests verify that get_by_id() and get_by_user_id() use joinedload() for single-query
eager loading of the blocks relationship.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with query tracking.

    Uses in-memory SQLite for fast, isolated testing.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Yield session
    async with session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def signal_chain_repository(db_session: AsyncSession) -> SQLAlchemySignalChainRepository:
    """Create a SignalChainRepository instance."""
    return SQLAlchemySignalChainRepository(db_session)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def signal_chain_with_blocks(
    db_session: AsyncSession,
    test_user: User,
) -> SignalChain:
    """Create a SignalChain ORM model with multiple blocks.

    Returns the ORM model (not entity) so tests can verify relationship loading.
    """
    # Create signal chain
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain",
        description="A test signal chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()

    # Create blocks
    block1 = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.PEDAL,
    )
    block2 = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    )
    block3 = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=2,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    )
    db_session.add(block1)
    db_session.add(block2)
    db_session.add(block3)
    await db_session.commit()

    return chain


async def test_signal_chain_get_by_id_single_query(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads blocks relationship in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for blocks
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 2 queries (1 + 1 relationship).
    """
    # Track executed queries
    query_count = 0

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        # Ignore SQLite internal queries (PRAGMA, etc)
        if not statement.strip().upper().startswith(('PRAGMA', 'BEGIN', 'COMMIT')):
            query_count += 1

    # Register query counter
    event.listen(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)

    try:
        # Execute get_by_id
        result = await signal_chain_repository.get_by_id(signal_chain_with_blocks.id)

        # Verify result is not None
        assert result is not None, "SignalChain should be found"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 2 queries (1 + 1 relationship)."
        )

        # Verify blocks are loaded (no lazy loading should occur)
        assert len(result.blocks) == 3, "Should have 3 blocks"

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_id_uses_unique_scalar_one_or_none(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() calls .unique().scalar_one_or_none().

    When using joinedload() with collections (1:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    result = await signal_chain_repository.get_by_id(signal_chain_with_blocks.id)

    assert result is not None
    # If .unique() wasn't called, we might get duplicate blocks
    assert len(result.blocks) == 3, "Should have exactly 3 blocks (no duplicates)"


async def test_get_by_user_id_single_query(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() loads blocks relationship in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for blocks
    - Returns fully hydrated entities without lazy loading

    This test MUST fail with selectinload() which fires 2 queries (1 + 1 relationship).
    """
    # Track executed queries
    query_count = 0

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        # Ignore SQLite internal queries (PRAGMA, etc)
        if not statement.strip().upper().startswith(('PRAGMA', 'BEGIN', 'COMMIT')):
            query_count += 1

    # Register query counter
    event.listen(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)

    try:
        # Execute get_by_user_id
        results = await signal_chain_repository.get_by_user_id(test_user.id)

        # Verify results are not empty
        assert len(results) > 0, "Should find signal chains for user"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 2 queries (1 + 1 relationship)."
        )

        # Verify blocks are loaded (no lazy loading should occur)
        assert len(results[0].blocks) == 3, "Should have 3 blocks"

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_user_id_uses_unique_scalars_all(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() calls .unique().scalars().all().

    When using joinedload() with collections (1:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    results = await signal_chain_repository.get_by_user_id(test_user.id)

    assert len(results) == 1, "Should have exactly 1 chain"
    # If .unique() wasn't called, we might get duplicate blocks
    assert len(results[0].blocks) == 3, "Should have exactly 3 blocks (no duplicates)"


async def test_get_by_id_blocks_relationship_loaded(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads blocks relationship without lazy loading.

    Verifies:
    - blocks relationship loaded (1:N)
    - blocks are ordered by position
    - all block attributes accessible without additional queries
    """
    result = await signal_chain_repository.get_by_id(signal_chain_with_blocks.id)

    assert result is not None

    # Verify blocks (1:N)
    assert len(result.blocks) == 3

    # Verify blocks are ordered by position
    positions = [block.position for block in result.blocks]
    assert positions == [0, 1, 2], "Blocks should be ordered by position"

    # Verify block attributes
    assert result.blocks[0].gear_type == GearType.PEDAL
    assert result.blocks[1].gear_type == GearType.AMP
    assert result.blocks[2].gear_type == GearType.IR


async def test_get_by_user_id_blocks_relationship_loaded(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    signal_chain_with_blocks: SignalChain,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() loads blocks relationship without lazy loading.

    Verifies:
    - blocks relationship loaded (1:N)
    - blocks are ordered by position
    - all block attributes accessible without additional queries
    """
    results = await signal_chain_repository.get_by_user_id(test_user.id)

    assert len(results) == 1
    chain = results[0]

    # Verify blocks (1:N)
    assert len(chain.blocks) == 3

    # Verify blocks are ordered by position
    positions = [block.position for block in chain.blocks]
    assert positions == [0, 1, 2], "Blocks should be ordered by position"

    # Verify block attributes
    assert chain.blocks[0].gear_type == GearType.PEDAL
    assert chain.blocks[1].gear_type == GearType.AMP
    assert chain.blocks[2].gear_type == GearType.IR


async def test_get_by_user_id_multiple_chains(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() correctly handles multiple chains with joinedload.

    Verifies that .unique() properly deduplicates when multiple chains
    each have multiple blocks.
    """
    # Create 2 chains with blocks
    chain1 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Chain 1",
        platform=Platform.NAM,
    )
    chain2 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Chain 2",
        platform=Platform.NAM,
    )
    db_session.add(chain1)
    db_session.add(chain2)
    await db_session.flush()

    # Add 2 blocks to chain1
    db_session.add(SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain1.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.PEDAL,
    ))
    db_session.add(SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain1.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    ))

    # Add 3 blocks to chain2
    db_session.add(SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain2.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.PEDAL,
    ))
    db_session.add(SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain2.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    ))
    db_session.add(SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain2.id,
        position=2,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    ))
    await db_session.commit()

    # Query all chains
    results = await signal_chain_repository.get_by_user_id(test_user.id)

    # Verify we got exactly 2 chains (not duplicated)
    assert len(results) == 2, "Should have exactly 2 chains (no duplicates from JOIN)"

    # Verify each chain has the correct number of blocks
    chain_blocks = {chain.name: len(chain.blocks) for chain in results}
    assert chain_blocks["Chain 1"] == 2, "Chain 1 should have 2 blocks"
    assert chain_blocks["Chain 2"] == 3, "Chain 2 should have 3 blocks"
