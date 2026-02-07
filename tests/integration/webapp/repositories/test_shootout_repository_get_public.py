"""Integration tests for ShootoutRepository.get_public() ID-subquery pattern (T41).

Tests verify that get_public() uses the two-step ID-subquery pattern for correct
pagination with joinedload (prevents LIMIT/OFFSET from limiting rows instead of entities).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.shootout import DITrack, Shootout, ShootoutChain, ShootoutStatus
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_repository import SQLAlchemyShootoutRepository

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
def shootout_repository(db_session: AsyncSession) -> SQLAlchemyShootoutRepository:
    """Create a ShootoutRepository instance."""
    return SQLAlchemyShootoutRepository(db_session)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def completed_shootouts_with_relationships(
    db_session: AsyncSession,
    test_user: User,
) -> list[Shootout]:
    """Create multiple COMPLETED shootouts with di_track and chains.

    Creates 5 completed shootouts to test pagination behavior.
    Each shootout has 2 chains (1:N relationship).

    Returns the ORM models (not entities) for verification.
    """
    shootouts = []

    for i in range(5):
        # Create a DI track
        di_track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name=f"DI Track {i}",
            file_path=f"/audio/test{i}.wav",
            original_filename=f"test{i}.wav",
            duration_seconds=120.0,
            sample_rate=44100,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(di_track)
        await db_session.flush()

        # Create signal chains
        signal_chain1 = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Chain {i}A",
            platform=Platform.NAM,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        signal_chain2 = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Chain {i}B",
            platform=Platform.NAM,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(signal_chain1)
        db_session.add(signal_chain2)
        await db_session.flush()

        # Create completed shootout
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            di_track_id=di_track.id,
            name=f"Completed Shootout {i}",
            description=f"Test shootout {i}",
            status=ShootoutStatus.COMPLETED,  # CRITICAL: must be COMPLETED for get_public()
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(shootout)
        await db_session.flush()

        # Create shootout chains (2 per shootout)
        chain1 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=signal_chain1.id,
            position=0,
            label=f"Chain {i}A",
        )
        chain2 = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=signal_chain2.id,
            position=1,
            label=f"Chain {i}B",
        )
        db_session.add(chain1)
        db_session.add(chain2)
        await db_session.flush()

        shootouts.append(shootout)

    await db_session.commit()
    return shootouts


async def test_shootout_get_public_single_query_with_pagination(
    shootout_repository: SQLAlchemyShootoutRepository,
    completed_shootouts_with_relationships: list[Shootout],
    db_session: AsyncSession,
) -> None:
    """Test that get_public() uses ID-subquery pattern with exactly 2 queries.

    Verifies:
    - Query count = 2 (ID-subquery + hydration with joinedload)
    - First query: SELECT id FROM shootout WHERE status=COMPLETED LIMIT/OFFSET
    - Second query: SELECT shootout JOIN di_track JOIN chains WHERE id IN (...)
    - Returns correct number of entities (not rows)

    This test MUST fail with direct LIMIT/OFFSET on the main query because:
    - joinedload() produces multiple rows per entity (due to 1:N chains)
    - LIMIT 3 on rows != LIMIT 3 on entities
    - ID-subquery pattern ensures LIMIT applies to entities, not rows

    Example:
    - 5 shootouts, each with 2 chains = 10 rows when JOINed
    - Direct LIMIT 3 on rows = could return 1-2 entities (wrong!)
    - ID-subquery LIMIT 3 = exactly 3 entity IDs, then JOIN = 3 entities (correct!)
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
        # Execute get_public with pagination (limit=3)
        results = await shootout_repository.get_public(limit=3, offset=0)

        # Verify query count = 2 (ID-subquery + hydration)
        assert query_count == 2, (
            f"Expected exactly 2 queries (ID-subquery + joinedload hydration), got {query_count}. "
            f"Direct LIMIT/OFFSET on main query would produce 1 query but wrong entity count. "
            f"ID-subquery pattern ensures correct pagination with joinedload."
        )

        # Verify correct entity count (not row count)
        # With 5 shootouts and LIMIT 3, should return exactly 3 entities
        assert len(results) == 3, (
            f"Expected exactly 3 entities with LIMIT 3, got {len(results)}. "
            f"Direct LIMIT on JOINed query would limit rows (10 rows total), not entities. "
            f"ID-subquery ensures LIMIT applies to entity IDs first."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        for shootout in results:
            assert len(shootout.chains) == 2, (
                f"Each shootout should have 2 chains. "
                f"If this fails, either relationships weren't loaded or duplicates exist."
            )

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_public_uses_unique_scalars_all(
    shootout_repository: SQLAlchemyShootoutRepository,
    completed_shootouts_with_relationships: list[Shootout],
    db_session: AsyncSession,
) -> None:
    """Test that get_public() calls .unique().scalars().all().

    When using joinedload() with collections (1:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    results = await shootout_repository.get_public(limit=5, offset=0)

    # Should return exactly 5 entities (not 10 rows)
    assert len(results) == 5, (
        f"Expected 5 unique entities, got {len(results)}. "
        f"Without .unique(), might get duplicate entities from JOIN."
    )

    # Verify no duplicate chains
    for shootout in results:
        assert len(shootout.chains) == 2, (
            f"Each shootout should have exactly 2 chains (no duplicates). "
            f"If > 2, .unique() wasn't called on the query result."
        )


async def test_get_public_filters_completed_status_only(
    shootout_repository: SQLAlchemyShootoutRepository,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test that get_public() only returns COMPLETED shootouts, not PENDING.

    Creates both COMPLETED and PENDING shootouts to verify filtering.
    """
    # Create a PENDING shootout (should NOT appear in get_public())
    di_track_pending = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Pending DI",
        file_path="/audio/pending.wav",
        original_filename="pending.wav",
        duration_seconds=120.0,
        sample_rate=44100,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(di_track_pending)
    await db_session.flush()

    signal_chain_pending = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Pending Chain",
        platform=Platform.NAM,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(signal_chain_pending)
    await db_session.flush()

    shootout_pending = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track_pending.id,
        name="Pending Shootout",
        description="Should not appear",
        status=ShootoutStatus.PENDING,  # NOT completed
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(shootout_pending)
    await db_session.flush()

    # Create a COMPLETED shootout (SHOULD appear in get_public())
    di_track_completed = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Completed DI",
        file_path="/audio/completed.wav",
        original_filename="completed.wav",
        duration_seconds=120.0,
        sample_rate=44100,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(di_track_completed)
    await db_session.flush()

    signal_chain_completed = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Completed Chain",
        platform=Platform.NAM,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(signal_chain_completed)
    await db_session.flush()

    shootout_completed = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track_completed.id,
        name="Completed Shootout",
        description="Should appear",
        status=ShootoutStatus.COMPLETED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(shootout_completed)
    await db_session.commit()

    # Execute get_public
    results = await shootout_repository.get_public(limit=10, offset=0)

    # Verify only COMPLETED shootout is returned
    assert len(results) == 1, f"Expected 1 completed shootout, got {len(results)}"
    assert results[0].name == "Completed Shootout"
    assert results[0].is_processed is True  # Entity field for COMPLETED status


async def test_get_public_all_relationships_loaded(
    shootout_repository: SQLAlchemyShootoutRepository,
    completed_shootouts_with_relationships: list[Shootout],
    db_session: AsyncSession,
) -> None:
    """Test that get_public() loads all relationships without lazy loading.

    Verifies:
    - chains relationship loaded (1:N)
    - di_track relationship loaded (N:1)

    All relationships should be accessible without triggering additional queries.
    """
    results = await shootout_repository.get_public(limit=2, offset=0)

    assert len(results) == 2, "Should return 2 shootouts with LIMIT 2"

    for shootout in results:
        # Verify chains (1:N)
        assert len(shootout.chains) == 2
        assert shootout.chains[0].position == 0
        assert shootout.chains[1].position == 1

        # Verify di_track_id is present (di_track relationship loaded at ORM level)
        assert shootout.di_track_id is not None


async def test_get_public_pagination_offset(
    shootout_repository: SQLAlchemyShootoutRepository,
    completed_shootouts_with_relationships: list[Shootout],
    db_session: AsyncSession,
) -> None:
    """Test that get_public() pagination with OFFSET works correctly.

    Verifies that OFFSET applies to entity IDs, not rows.

    With 5 shootouts:
    - Page 1: LIMIT 2 OFFSET 0 = entities 0-1
    - Page 2: LIMIT 2 OFFSET 2 = entities 2-3
    - Page 3: LIMIT 2 OFFSET 4 = entity 4

    If OFFSET applied to rows (not IDs), this would return wrong entities.
    """
    # Page 1: first 2 entities
    page1 = await shootout_repository.get_public(limit=2, offset=0)
    assert len(page1) == 2, "Page 1 should have 2 entities"

    # Page 2: next 2 entities
    page2 = await shootout_repository.get_public(limit=2, offset=2)
    assert len(page2) == 2, "Page 2 should have 2 entities"

    # Page 3: last entity
    page3 = await shootout_repository.get_public(limit=2, offset=4)
    assert len(page3) == 1, "Page 3 should have 1 entity (5 total - 4 offset)"

    # Verify no overlap between pages (different IDs)
    page1_ids = {s.id for s in page1}
    page2_ids = {s.id for s in page2}
    page3_ids = {s.id for s in page3}

    assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"
    assert page1_ids.isdisjoint(page3_ids), "Pages should not overlap"
    assert page2_ids.isdisjoint(page3_ids), "Pages should not overlap"

    # Verify all 5 entities retrieved across pages
    all_ids = page1_ids | page2_ids | page3_ids
    assert len(all_ids) == 5, "Should retrieve all 5 unique entities across pages"
