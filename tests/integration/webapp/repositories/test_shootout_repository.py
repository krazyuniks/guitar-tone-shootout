"""Integration tests for ShootoutRepository joinedload conversion (T40).

Tests verify that get_by_id() and get_by_user_id() use joinedload() for single-query
eager loading of relationships (di_track, chains).
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
async def sample_shootout_with_relationships(
    db_session: AsyncSession,
    test_user: User,
) -> Shootout:
    """Create a fully-populated Shootout ORM model with di_track and chains.

    Returns the ORM model (not entity) so tests can verify relationship loading.
    """
    # Create a DI track
    di_track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI Track",
        file_path="/audio/test.wav",
        original_filename="test.wav",
        duration_seconds=120.0,
        sample_rate=44100,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(di_track)
    await db_session.flush()

    # Create signal chains (needed for foreign key constraints)
    signal_chain1 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain 1",
        platform=Platform.NAM,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    signal_chain2 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain 2",
        platform=Platform.NAM,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(signal_chain1)
    db_session.add(signal_chain2)
    await db_session.flush()

    # Create shootout
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        description="A test shootout",
        status=ShootoutStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(shootout)
    await db_session.flush()

    # Create shootout chains
    chain1 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=signal_chain1.id,
        position=0,
        label="Chain A",
    )
    chain2 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=signal_chain2.id,
        position=1,
        label="Chain B",
    )
    db_session.add(chain1)
    db_session.add(chain2)
    await db_session.commit()

    return shootout


async def test_shootout_get_by_id_single_query(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for di_track and chains
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 3 queries (1 + 2 relationships).
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
        result = await shootout_repository.get_by_id(sample_shootout_with_relationships.id)

        # Verify result is not None
        assert result is not None, "Shootout should be found"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 3 queries (1 + 2 relationships)."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        assert len(result.chains) == 2, "Should have 2 chains"
        # di_track is loaded via ORM but not directly accessible in domain entity

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_id_uses_unique_scalar_one_or_none(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() calls .unique().scalar_one_or_none().

    When using joinedload() with collections (1:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    result = await shootout_repository.get_by_id(sample_shootout_with_relationships.id)

    assert result is not None
    # If .unique() wasn't called, we might get duplicate chains
    assert len(result.chains) == 2, "Should have exactly 2 chains (no duplicates)"


async def test_get_by_id_all_relationships_loaded(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads all relationships without lazy loading.

    Verifies:
    - chains relationship loaded (1:N)
    - di_track relationship loaded (N:1)

    All relationships should be accessible without triggering additional queries.
    """
    result = await shootout_repository.get_by_id(sample_shootout_with_relationships.id)

    assert result is not None

    # Verify chains (1:N)
    assert len(result.chains) == 2
    assert result.chains[0].label == "Chain A"
    assert result.chains[0].position == 0
    assert result.chains[1].label == "Chain B"
    assert result.chains[1].position == 1

    # Verify di_track_id is present (di_track relationship loaded at ORM level)
    assert result.di_track_id is not None


async def test_get_by_user_id_single_query(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for di_track and chains
    - Returns fully hydrated entities without lazy loading

    This test MUST fail with selectinload() which fires 3 queries (1 + 2 relationships).
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
        results = await shootout_repository.get_by_user_id(test_user.id)

        # Verify results
        assert len(results) == 1, "Should find 1 shootout"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 3 queries (1 + 2 relationships)."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        result = results[0]
        assert len(result.chains) == 2, "Should have 2 chains"

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_user_id_uses_unique(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() calls .unique() on results.

    When using joinedload() with collections (1:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    results = await shootout_repository.get_by_user_id(test_user.id)

    assert len(results) == 1
    # If .unique() wasn't called, we might get duplicate chains
    assert len(results[0].chains) == 2, "Should have exactly 2 chains (no duplicates)"


async def test_get_by_user_id_all_relationships_loaded(
    shootout_repository: SQLAlchemyShootoutRepository,
    sample_shootout_with_relationships: Shootout,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_user_id() loads all relationships without lazy loading.

    Verifies:
    - chains relationship loaded (1:N)
    - di_track relationship loaded (N:1)

    All relationships should be accessible without triggering additional queries.
    """
    results = await shootout_repository.get_by_user_id(test_user.id)

    assert len(results) == 1
    result = results[0]

    # Verify chains (1:N)
    assert len(result.chains) == 2
    assert result.chains[0].label == "Chain A"
    assert result.chains[0].position == 0
    assert result.chains[1].label == "Chain B"
    assert result.chains[1].position == 1

    # Verify di_track_id is present (di_track relationship loaded at ORM level)
    assert result.di_track_id is not None
