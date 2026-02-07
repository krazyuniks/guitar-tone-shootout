"""Integration tests for GearRepository.get_by_source() - verifying single query pattern (T43).

Tests verify that get_by_source() uses joinedload() for all relationships in a single query,
not selectinload() which would fire 5 queries (1 main + 4 relationships).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import (
    GearType,
    ModelSize,
    Platform,
)
from tests.fixtures.query_counter import assert_query_count
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import (
    Gear,
    GearMake,
    GearModel,
    GearSource,
    GearTag,
    gear_tags_table,
)
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
async def gear_with_source(
    db_session: AsyncSession,
) -> tuple[str, str]:
    """Create a Gear item with all 4 relationships populated, looked up via source.

    Returns:
        Tuple of (source_name, source_record_id) for lookup
    """
    # Create a make
    make = GearMake(id=uuid4(), name="Fender")
    db_session.add(make)
    await db_session.flush()

    # Create source
    source = GearSource(
        id=uuid4(),
        source_name="t3k",
        source_record_id="test-amp-123",
        source_updated_at=datetime.now(UTC),
    )
    db_session.add(source)
    await db_session.flush()

    # Create gear
    gear = Gear(
        id=uuid4(),
        name="Blues Jr",
        slug="fender-blues-jr",
        gear_type=GearType.AMP,
        description="Classic tube amp",
        manufacturer="Fender",
        make_id=make.id,
        source_id=source.id,
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create 2 models
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

    # Create 2 tags
    tag1 = GearTag(id=uuid4(), name="tube")
    tag2 = GearTag(id=uuid4(), name="vintage")
    db_session.add(tag1)
    db_session.add(tag2)
    await db_session.flush()

    # Associate tags with gear (many-to-many)
    await db_session.execute(
        insert(gear_tags_table).values(gear_id=gear.id, tag_id=tag1.id)
    )
    await db_session.execute(
        insert(gear_tags_table).values(gear_id=gear.id, tag_id=tag2.id)
    )

    await db_session.commit()
    return ("t3k", "test-amp-123")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gear_get_by_source_single_query(
    gear_repository: SQLAlchemyGearRepository,
    gear_with_source: tuple[str, str],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_source() executes exactly 1 query with all relationships.

    Verifies:
    - Query count = 1 (single query with joinedload for all relationships)
    - No additional queries fired by relationship access
    - All 4 relationships loaded: models (1:N), tags (M:N), source (1:1), make (N:1)

    This test MUST fail if selectinload() is used, which would produce 5 queries
    (1 main + 4 relationships).

    CURRENT STATE: get_by_source() uses selectinload() which fires 5 queries.
    This test will FAIL until it's changed to joinedload() with .unique().
    """
    from sqlalchemy import event

    source_name, source_record_id = gear_with_source

    # Track ALL queries including selectinload queries
    query_count = 0

    def count_all_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    # Get the engine
    bind = db_session.get_bind()
    if hasattr(bind, "sync_engine"):
        engine = bind.sync_engine
    else:
        engine = bind

    event.listen(engine, "before_cursor_execute", count_all_queries)

    try:
        # Execute get_by_source
        gear = await gear_repository.get_by_source(source_name, source_record_id)

        # Verify gear was found
        assert gear is not None, "Gear should be found"
        assert gear.name == "Blues Jr"

        # Access all relationships - should NOT fire additional queries
        # These assertions also verify the relationships are fully loaded

        # 1. models (1:N)
        assert len(gear.models) == 2, "Should have 2 models"
        assert all(m.platform == Platform.NAM for m in gear.models)

        # 2. tags (M:N)
        assert len(gear.tags) == 2, "Should have 2 tags"
        assert set(gear.tags) == {"tube", "vintage"}

        # 3. source (1:1)
        assert gear.source is not None, "Should have source"
        assert gear.source.source_name == "t3k"
        assert gear.source.source_record_id == "test-amp-123"

        # CRITICAL: This should be 1 with joinedload, but will be 5 with selectinload
        assert query_count == 1, (
            f"Expected 1 query with joinedload(), got {query_count} queries. "
            f"selectinload() fires 1 main + 4 relationship queries = 5 total."
        )

    finally:
        event.remove(engine, "before_cursor_execute", count_all_queries)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gear_get_by_source_uses_unique(
    gear_repository: SQLAlchemyGearRepository,
    gear_with_source: tuple[str, str],
    db_session: AsyncSession,
) -> None:
    """Test that get_by_source() uses .unique() to deduplicate JOIN results.

    When using joinedload() with collections (1:N, M:N), JOINs produce duplicate
    parent rows that must be de-duplicated with .unique().

    This test verifies that accessing relationships doesn't return duplicate entities.

    CURRENT STATE: get_by_source() uses selectinload() which doesn't need .unique()
    because it fires separate queries. This test will PASS now but ensures the
    behavior is maintained when switching to joinedload().
    """
    source_name, source_record_id = gear_with_source
    gear = await gear_repository.get_by_source(source_name, source_record_id)

    assert gear is not None

    # Verify no duplicate models
    model_ids = [m.id for m in gear.models]
    assert len(model_ids) == len(set(model_ids)), "Should have no duplicate models"

    # Verify no duplicate tags
    tag_names = gear.tags
    assert len(tag_names) == len(set(tag_names)), "Should have no duplicate tags"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gear_get_by_source_nonexistent_returns_none(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> None:
    """Test that get_by_source() returns None for nonexistent source."""
    with assert_query_count(db_session, expected=1):
        gear = await gear_repository.get_by_source("t3k", "nonexistent-id")
        assert gear is None
