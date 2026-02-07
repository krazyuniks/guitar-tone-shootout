"""Integration tests for GearRepository search() ID-subquery pattern (T36).

Tests verify that search() uses two-step ID-subquery pattern for paginated queries:
1. Step 1: ID-subquery with LIMIT/OFFSET to resolve correct page of IDs
2. Step 2: Hydration query with joinedload() for all relationships

This prevents row multiplication from JOINs affecting pagination.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
async def multiple_gear_items(
    db_session: AsyncSession,
) -> list[Gear]:
    """Create multiple Gear items with all relationships for pagination testing.

    Creates 5 gear items, each with:
    - 2 models (1:N relationship)
    - 2 tags (M:N relationship)
    - 1 source (1:1 relationship)
    - 1 make (N:1 relationship)

    Returns ORM models (not entities) for verification.
    """
    # Create a make
    make = GearMake(id=uuid4(), name="Fender")
    db_session.add(make)
    await db_session.flush()

    gear_items = []

    for i in range(5):
        # Create source
        source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id=f"test-{i}",
            source_updated_at=datetime.now(UTC),
        )
        db_session.add(source)
        await db_session.flush()

        # Create gear
        gear = Gear(
            id=uuid4(),
            name=f"Gear Item {i}",
            slug=f"gear-item-{i}",
            gear_type=GearType.AMP,
            description=f"Test gear {i}",
            manufacturer="Fender",
            make_id=make.id,
            source_id=source.id,
            is_public=True,
        )
        db_session.add(gear)
        await db_session.flush()

        # Create 2 models per gear
        for j in range(2):
            model = GearModel(
                id=uuid4(),
                gear_id=gear.id,
                platform=Platform.NAM,
                size=ModelSize.STANDARD if j == 0 else ModelSize.LITE,
                download_url=f"https://example.com/gear{i}-model{j}.nam",
                download_status=DownloadStatus.PENDING,
            )
            db_session.add(model)
        await db_session.flush()

        # Create 2 tags per gear
        tag1 = GearTag(id=uuid4(), name=f"tag-{i}-a")
        tag2 = GearTag(id=uuid4(), name=f"tag-{i}-b")
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

        gear_items.append(gear)

    await db_session.commit()
    return gear_items


async def test_gear_search_single_query_with_pagination(
    gear_repository: SQLAlchemyGearRepository,
    multiple_gear_items: list[Gear],
    db_session: AsyncSession,
) -> None:
    """Test that search() uses ID-subquery pattern with exactly 2 queries.

    Verifies:
    - Query count = 2 (ID subquery + hydration query)
    - First query: SELECT Gear.id with LIMIT/OFFSET
    - Second query: SELECT Gear with joinedload() WHERE id IN (...)
    - No additional queries fired by relationship access

    This test MUST fail with direct LIMIT/OFFSET + selectinload() which would fire
    6 queries (1 main + 5 relationships) and return wrong entity count due to
    row multiplication from JOINs.
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
        # Execute search with pagination
        results = await gear_repository.search(limit=3, offset=0)

        # Verify result count (entities, not rows)
        assert len(results) == 3, (
            f"Expected 3 entities, got {len(results)}. "
            f"Direct LIMIT/OFFSET with JOINs would count rows, not entities."
        )

        # Verify query count = 2 (CRITICAL: ID subquery + hydration)
        assert query_count == 2, (
            f"Expected exactly 2 queries (ID subquery + hydration), got {query_count}. "
            f"Direct LIMIT/OFFSET + selectinload() would produce 6 queries (1 + 5 relationships)."
        )

        # Verify all relationships are loaded (no lazy loading should occur)
        for gear in results:
            assert len(gear.models) == 2, f"Gear {gear.name} should have 2 models"
            assert len(gear.tags) == 2, f"Gear {gear.name} should have 2 tags"
            assert gear.source is not None, f"Gear {gear.name} should have source"

    finally:
        # Cleanup event listener
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_search_uses_unique_scalars_all(
    gear_repository: SQLAlchemyGearRepository,
    multiple_gear_items: list[Gear],
    db_session: AsyncSession,
) -> None:
    """Test that search() calls .unique().scalars().all().

    When using joinedload() with collections (1:N, M:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies:
    - No duplicate entities in results
    - Correct entity count (not row count)
    - Each entity has correct relationship counts (no duplicates)
    """
    results = await gear_repository.search(limit=5, offset=0)

    # Verify no duplicate entities
    result_ids = [gear.id for gear in results]
    assert len(result_ids) == len(set(result_ids)), "Should have no duplicate entities"

    # Verify correct entity count
    assert len(results) == 5, "Should return 5 distinct entities"

    # Verify each entity has correct relationship counts (no duplicates from JOIN)
    for gear in results:
        assert len(gear.models) == 2, (
            f"Gear {gear.name} should have exactly 2 models (no duplicates). "
            f"Without .unique(), JOINs produce duplicate rows."
        )
        assert len(gear.tags) == 2, (
            f"Gear {gear.name} should have exactly 2 tags (no duplicates). "
            f"Without .unique(), JOINs produce duplicate rows."
        )


async def test_search_pagination_returns_correct_entity_count(
    gear_repository: SQLAlchemyGearRepository,
    multiple_gear_items: list[Gear],
    db_session: AsyncSession,
) -> None:
    """Test that pagination returns correct entity count, not row count.

    With direct LIMIT/OFFSET + JOINs, row multiplication affects pagination:
    - 5 entities * 2 models = 10 rows
    - 10 rows * 2 tags = 20 rows
    - LIMIT 3 would return first 3 ROWS (part of entity 0 only)

    With ID-subquery pattern:
    - LIMIT 3 applies to entity IDs
    - Hydration query fetches 3 complete entities
    """
    # Page 1: entities 0-2
    page1 = await gear_repository.search(limit=3, offset=0)
    assert len(page1) == 3, "Page 1 should have 3 entities"
    assert page1[0].name == "Gear Item 0"
    assert page1[1].name == "Gear Item 1"
    assert page1[2].name == "Gear Item 2"

    # Page 2: entities 3-4
    page2 = await gear_repository.search(limit=3, offset=3)
    assert len(page2) == 2, "Page 2 should have 2 entities (only 5 total)"
    assert page2[0].name == "Gear Item 3"
    assert page2[1].name == "Gear Item 4"


async def test_search_loads_all_four_relationships_with_joinedload(
    gear_repository: SQLAlchemyGearRepository,
    multiple_gear_items: list[Gear],
    db_session: AsyncSession,
) -> None:
    """Test that search() uses joinedload() for all 4 relationships.

    Verifies:
    - models relationship loaded (1:N)
    - tags relationship loaded (M:N)
    - source relationship loaded (1:1)
    - make relationship loaded (N:1) - not exposed in domain entity

    All relationships should be accessible without triggering additional queries.
    """
    # Track queries to ensure no lazy loading
    query_count = 0

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if not statement.strip().upper().startswith(('PRAGMA', 'BEGIN', 'COMMIT')):
            query_count += 1

    event.listen(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)

    try:
        results = await gear_repository.search(limit=2, offset=0)

        # Should have fired 2 queries (ID subquery + hydration)
        assert query_count == 2

        # Access all relationships - should NOT fire additional queries
        for gear in results:
            # Access models (1:N)
            assert len(gear.models) == 2
            assert all(m.platform == Platform.NAM for m in gear.models)

            # Access tags (M:N)
            assert len(gear.tags) == 2

            # Access source (1:1)
            assert gear.source is not None
            assert gear.source.source_name == "t3k"

        # Verify no additional queries fired
        assert query_count == 2, (
            f"Expected 2 queries total, got {query_count}. "
            f"Additional queries indicate lazy loading (missing joinedload)."
        )

    finally:
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)


async def test_search_with_filters_uses_id_subquery(
    gear_repository: SQLAlchemyGearRepository,
    multiple_gear_items: list[Gear],
    db_session: AsyncSession,
) -> None:
    """Test that search() with filters still uses ID-subquery pattern.

    Verifies:
    - Filters applied to ID subquery (first step)
    - Hydration query loads full entities (second step)
    - Query count = 2
    """
    query_count = 0

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if not statement.strip().upper().startswith(('PRAGMA', 'BEGIN', 'COMMIT')):
            query_count += 1

    event.listen(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)

    try:
        # Search with gear_type filter
        results = await gear_repository.search(
            gear_type=GearType.AMP,
            limit=3,
            offset=0,
        )

        # Should still use 2 queries
        assert query_count == 2, (
            f"Expected 2 queries with filters, got {query_count}"
        )

        # Should return filtered results
        assert len(results) == 3
        assert all(gear.gear_type == GearType.AMP for gear in results)

        # All relationships should be loaded
        for gear in results:
            assert len(gear.models) == 2
            assert len(gear.tags) == 2
            assert gear.source is not None

    finally:
        event.remove(db_session.sync_session.get_bind(), "before_cursor_execute", count_queries)
