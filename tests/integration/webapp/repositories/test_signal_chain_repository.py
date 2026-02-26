"""Integration tests for SignalChainRepository query patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


from uuid import uuid4

import pytest
from sqlalchemy import event

from gts.domain.entities.signal_chain import SignalChain as SignalChainEntity
from gts.domain.entities.signal_chain import SignalChainBlock as BlockEntity
from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)


class QueryCounter:
    """Context manager to count SQL queries executed."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.count = 0

    def __enter__(self):
        """Start counting queries."""
        self.count = 0
        event.listen(self.engine.sync_engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop counting queries."""
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._before_cursor_execute)

    def _before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        """Callback fired before each query execution. Excludes SAVEPOINT statements."""
        if statement.strip().upper().startswith("SAVEPOINT"):
            return
        self.count += 1


@pytest.fixture
async def db_engine(core_engine: AsyncEngine) -> AsyncEngine:
    """Alias core_engine for QueryCounter compatibility."""
    return core_engine


@pytest.fixture
def signal_chain_repository(db_session: AsyncSession) -> SQLAlchemySignalChainRepository:
    """Create a SignalChainRepository instance."""
    return SQLAlchemySignalChainRepository(db_session)


@pytest.fixture
async def sample_signal_chain_with_blocks(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    db_session: AsyncSession,
) -> SignalChainEntity:
    """Create and persist a signal chain with blocks."""
    # Import here to avoid circular dependency
    from webapp.adapters.persistence.models.user import User

    # Create a user first to satisfy foreign key constraint
    suffix = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"testuser_{suffix}",
        email=f"test_{suffix}@example.com",
    )
    db_session.add(user)
    await db_session.flush()

    chain = SignalChainEntity(
        id=uuid4(),
        user_id=user.id,
        name="Test Chain",
        description="A test signal chain",
        platform=Platform.NAM,
    )

    # Add blocks: pedal -> amp -> IR -> post effect
    block1 = BlockEntity(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.PEDAL,
    )
    block2 = BlockEntity(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    )
    block3 = BlockEntity(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=2,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    )
    block4 = BlockEntity(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=3,
        user_gear_id=uuid4(),
        gear_type=GearType.POST_EFFECT,
    )

    chain.add_block(block1)
    chain.add_block(block2)
    chain.add_block(block3)
    chain.add_block(block4)

    await signal_chain_repository.save(chain)
    await db_session.commit()

    return chain


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_chain_get_by_id_single_query(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    db_session: AsyncSession,
    db_engine: AsyncEngine,
    sample_signal_chain_with_blocks: SignalChainEntity,
) -> None:
    """Verify get_by_id loads all relationships in a single query.

    Citation: .claude/rules/query-patterns.md:51-71

    Tests that get_by_id() uses joinedload for:
    - SignalChain.blocks (1:N)

    Expected: 1 SQL query total (not 1 + 1 separate queries).
    """
    # Expire all objects to force fresh query
    db_session.expire_all()

    # Count queries during get_by_id
    with QueryCounter(db_engine) as counter:
        result = await signal_chain_repository.get_by_id(sample_signal_chain_with_blocks.id)

    # Verify chain loaded
    assert result is not None
    assert result.id == sample_signal_chain_with_blocks.id

    # Verify all relationships loaded without additional queries
    assert result.name == "Test Chain"
    assert result.description == "A test signal chain"
    assert result.platform == Platform.NAM
    assert len(result.blocks) == 4

    # Verify blocks are ordered correctly
    assert result.blocks[0].gear_type == GearType.PEDAL
    assert result.blocks[1].gear_type == GearType.AMP
    assert result.blocks[2].gear_type == GearType.IR
    assert result.blocks[3].gear_type == GearType.POST_EFFECT

    # Critical assertion: only ONE query executed
    assert counter.count == 1, f"Expected 1 query, got {counter.count}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_chain_get_by_id_uses_unique(
    signal_chain_repository: SQLAlchemySignalChainRepository,
    db_session: AsyncSession,
    sample_signal_chain_with_blocks: SignalChainEntity,
) -> None:
    """Verify get_by_id calls .unique() to deduplicate joined rows.

    Citation: .claude/rules/query-patterns.md:60

    When using joinedload with collections (1:N, M:N), JOINs produce
    duplicate parent rows that must be de-duplicated with .unique().
    """
    # Expire all objects
    db_session.expire_all()

    # Execute get_by_id
    result = await signal_chain_repository.get_by_id(sample_signal_chain_with_blocks.id)

    # Verify no duplicates: should return single entity, not multiple
    assert result is not None
    assert isinstance(result, SignalChainEntity)

    # Verify blocks collection is properly loaded (not duplicated)
    assert len(result.blocks) == 4
