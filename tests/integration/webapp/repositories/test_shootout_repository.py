"""Integration tests for ShootoutRepository query patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.shootout import Shootout as ShootoutEntity
from core.domain.entities.shootout import ShootoutChain as ShootoutChainVO
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.repositories.shootout_repository import SQLAlchemyShootoutRepository

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime


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
        """Callback fired before each query execution."""
        self.count += 1


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
def shootout_repository(db_session: AsyncSession) -> SQLAlchemyShootoutRepository:
    """Create a ShootoutRepository instance."""
    return SQLAlchemyShootoutRepository(db_session)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_get_public_single_query_with_pagination(
    shootout_repository: SQLAlchemyShootoutRepository,
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    """Verify get_public() uses ID-subquery pattern for pagination.

    Citation: .claude/rules/query-patterns.md:73-98
    Acceptance Criteria: T41 - query count = 2, correct entity count

    Tests that get_public() uses two-step ID-subquery pattern:
    1. ID query: SELECT Shootout.id ... WHERE is_processed = true LIMIT X OFFSET Y
    2. Hydration query: SELECT Shootout.* ... WHERE Shootout.id IN (...) with joinedload

    Expected: 2 SQL queries total (ID subquery + hydration query).
    This avoids pagination issues where LIMIT/OFFSET on joined rows
    limits rows instead of entities.
    """
    # Create test data: 10 processed shootouts with di_track and chains
    from datetime import UTC, datetime

    # First, create users for the shootouts
    from webapp.adapters.persistence.models.user import User
    test_user = User(
        id=uuid4(),
        username="test_user",
        email="test@example.com",
    )
    db_session.add(test_user)

    # Create DI tracks
    from webapp.adapters.persistence.models.shootout import DITrack
    di_tracks = []
    for i in range(10):
        di_track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name=f"DI Track {i:02d}",
            file_path=f"/audio/di-track-{i}.wav",
            original_filename=f"di-track-{i}.wav",
            duration_seconds=30.0,
            sample_rate=44100,
        )
        db_session.add(di_track)
        di_tracks.append(di_track)

    # Create signal chains for shootout chains
    from core.domain.value_objects.signal_chain_enums import Platform
    from webapp.adapters.persistence.models.signal_chain import SignalChain
    signal_chains = []
    for i in range(20):  # 20 chains total (2 per shootout)
        chain = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Signal Chain {i:02d}",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        signal_chains.append(chain)

    # Create 10 processed shootouts
    from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
    for i in range(10):
        shootout_entity = ShootoutEntity(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Test Shootout {i:02d}",
            di_track_id=di_tracks[i].id,
            description=f"Test shootout {i}",
        )
        # Mark as processed (required for get_public)
        shootout_entity.mark_processed(output_path=f"/videos/shootout-{i}.mp4")

        # Add 2 chains to each shootout (creates 1:N relationship for joins)
        chain1 = ShootoutChainVO(
            id=uuid4(),
            shootout_id=shootout_entity.id,
            signal_chain_id=signal_chains[i * 2].id,
            position=0,
            label=f"Chain A-{i}",
        )
        chain2 = ShootoutChainVO(
            id=uuid4(),
            shootout_id=shootout_entity.id,
            signal_chain_id=signal_chains[i * 2 + 1].id,
            position=1,
            label=f"Chain B-{i}",
        )
        shootout_entity.add_chain(chain1)
        shootout_entity.add_chain(chain2)

        await shootout_repository.save(shootout_entity)

    await db_session.commit()

    # Expire all objects to force fresh queries
    db_session.expire_all()

    # Execute get_public with pagination
    with QueryCounter(db_engine) as counter:
        results = await shootout_repository.get_public(
            limit=5,
            offset=0,
        )

    # Acceptance Criteria: query count = 2 (ID subquery + hydration query)
    assert counter.count == 2, f"Expected 2 queries (ID + hydration), got {counter.count}"

    # Acceptance Criteria: correct entity count (not row count)
    assert len(results) == 5, f"Expected 5 entities, got {len(results)}"

    # Verify all relationships loaded via joinedload (di_track and chains)
    for shootout in results:
        # di_track relationship loaded
        assert shootout.di_track_id is not None, "Shootout should have di_track_id"
        # chains relationship loaded (each shootout has 2 chains)
        assert len(shootout.chains) == 2, f"Expected 2 chains, got {len(shootout.chains)}"

    # Verify correct shootouts returned (processed only, ordered by created_at desc)
    assert all(s.is_processed for s in results), "All returned shootouts should be processed"
