"""Integration tests for GearRepository joinedload conversion (T35).

Tests verify that get_by_id() and get_by_slug() use joinedload() for single-query
eager loading of all relationships (models, tags, make, source).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.gear import Gear as GearEntity
from core.domain.entities.gear import GearModel as GearModelVO
from core.domain.entities.gear import GearSource as GearSourceVO
from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import (
    GearType,
    ModelSize,
    Platform,
)
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear, GearMake, GearModel, GearSource, GearTag
from webapp.adapters.persistence.repositories.gear_repository import SQLAlchemyGearRepository

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
def gear_repository(db_session: AsyncSession) -> SQLAlchemyGearRepository:
    """Create a GearRepository instance."""
    return SQLAlchemyGearRepository(db_session)


@pytest.fixture
async def sample_gear_with_all_relationships(
    db_session: AsyncSession,
) -> Gear:
    """Create a fully-populated Gear ORM model with all 4 relationships.

    Returns the ORM model (not entity) so tests can verify relationship loading.
    """
    # Create a make
    make = GearMake(id=uuid4(), name="Fender")
    db_session.add(make)
    await db_session.flush()

    # Create a source
    source = GearSource(
        id=uuid4(),
        source_name="t3k",
        source_record_id="test-123",
        source_updated_at=datetime.now(UTC),
    )
    db_session.add(source)
    await db_session.flush()

    # Create gear
    gear = Gear(
        id=uuid4(),
        name="Fender Deluxe Reverb",
        slug="fender-deluxe-reverb",
        gear_type=GearType.AMP,
        description="Classic tube amp",
        manufacturer="Fender",
        make_id=make.id,
        source_id=source.id,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create models
    model1 = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        download_url="https://example.com/model1.nam",
        download_status=DownloadStatus.PENDING,
    )
    model2 = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.LITE,
        download_url="https://example.com/model2.nam",
        download_status=DownloadStatus.PENDING,
    )
    db_session.add(model1)
    db_session.add(model2)
    await db_session.flush()

    # Create tags
    tag1 = GearTag(id=uuid4(), name="clean")
    tag2 = GearTag(id=uuid4(), name="vintage")
    db_session.add(tag1)
    db_session.add(tag2)
    await db_session.flush()

    # Associate tags with gear (many-to-many)
    from sqlalchemy import insert
    from webapp.adapters.persistence.models.gear import gear_tags_table

    await db_session.execute(
        insert(gear_tags_table).values(gear_id=gear.id, tag_id=tag1.id)
    )
    await db_session.execute(
        insert(gear_tags_table).values(gear_id=gear.id, tag_id=tag2.id)
    )
    await db_session.commit()

    return gear


async def test_get_by_id_single_query(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for models, tags, make, source
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 5 queries (1 + 4 relationships).
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
        result = await gear_repository.get_by_id(sample_gear_with_all_relationships.id)

        # Verify result is not None
        assert result is not None, "Gear should be found"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 5 queries (1 + 4 relationships)."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        assert len(result.models) == 2, "Should have 2 models"
        assert len(result.tags) == 2, "Should have 2 tags"
        assert result.source is not None, "Should have source"
        # Note: make is not exposed in the domain entity, but is loaded at ORM level

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_id_uses_unique_scalar_one_or_none(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() calls .unique().scalar_one_or_none().

    When using joinedload() with collections (1:N, M:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    result = await gear_repository.get_by_id(sample_gear_with_all_relationships.id)

    assert result is not None
    # If .unique() wasn't called, we might get duplicate models/tags
    assert len(result.models) == 2, "Should have exactly 2 models (no duplicates)"
    assert len(result.tags) == 2, "Should have exactly 2 tags (no duplicates)"


async def test_get_by_slug_single_query(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_slug() loads all relationships in a single SQL query.

    Verifies:
    - Query count = 1 (no N+1 queries)
    - Uses joinedload() for models, tags, make, source
    - Returns fully hydrated entity without lazy loading

    This test MUST fail with selectinload() which fires 5 queries (1 + 4 relationships).
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
        # Execute get_by_slug
        result = await gear_repository.get_by_slug("fender-deluxe-reverb")

        # Verify result is not None
        assert result is not None, "Gear should be found by slug"

        # Verify query count = 1 (CRITICAL: this will fail with selectinload)
        assert query_count == 1, (
            f"Expected exactly 1 query with joinedload(), got {query_count}. "
            f"selectinload() would produce 5 queries (1 + 4 relationships)."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        assert len(result.models) == 2, "Should have 2 models"
        assert len(result.tags) == 2, "Should have 2 tags"
        assert result.source is not None, "Should have source"

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_get_by_slug_uses_unique_scalar_one_or_none(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_slug() calls .unique().scalar_one_or_none().

    When using joinedload() with collections (1:N, M:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies the method chain is correct.
    """
    # This test will pass only if .unique() is called
    result = await gear_repository.get_by_slug("fender-deluxe-reverb")

    assert result is not None
    # If .unique() wasn't called, we might get duplicate models/tags
    assert len(result.models) == 2, "Should have exactly 2 models (no duplicates)"
    assert len(result.tags) == 2, "Should have exactly 2 tags (no duplicates)"


async def test_get_by_id_all_relationships_loaded(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_id() loads all 4 relationships without lazy loading.

    Verifies:
    - models relationship loaded (1:N)
    - tags relationship loaded (M:N)
    - source relationship loaded (1:1)
    - make relationship loaded (N:1) - not exposed in domain entity

    All relationships should be accessible without triggering additional queries.
    """
    result = await gear_repository.get_by_id(sample_gear_with_all_relationships.id)

    assert result is not None

    # Verify models (1:N)
    assert len(result.models) == 2
    assert all(m.platform == Platform.NAM for m in result.models)
    assert {m.size for m in result.models} == {ModelSize.STANDARD, ModelSize.LITE}

    # Verify tags (M:N)
    assert len(result.tags) == 2
    assert set(result.tags) == {"clean", "vintage"}

    # Verify source (1:1)
    assert result.source is not None
    assert result.source.source_name == "t3k"
    assert result.source.source_record_id == "test-123"

    # Note: make (N:1) is not exposed in domain entity but is loaded at ORM level


async def test_get_by_slug_all_relationships_loaded(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_all_relationships: Gear,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_slug() loads all 4 relationships without lazy loading.

    Verifies:
    - models relationship loaded (1:N)
    - tags relationship loaded (M:N)
    - source relationship loaded (1:1)
    - make relationship loaded (N:1) - not exposed in domain entity

    All relationships should be accessible without triggering additional queries.
    """
    result = await gear_repository.get_by_slug("fender-deluxe-reverb")

    assert result is not None

    # Verify models (1:N)
    assert len(result.models) == 2
    assert all(m.platform == Platform.NAM for m in result.models)
    assert {m.size for m in result.models} == {ModelSize.STANDARD, ModelSize.LITE}

    # Verify tags (M:N)
    assert len(result.tags) == 2
    assert set(result.tags) == {"clean", "vintage"}

    # Verify source (1:1)
    assert result.source is not None
    assert result.source.source_name == "t3k"
    assert result.source.source_record_id == "test-123"

    # Note: make (N:1) is not exposed in domain entity but is loaded at ORM level
