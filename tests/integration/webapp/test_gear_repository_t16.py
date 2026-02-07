"""Integration tests for T16: Gear Repository - Get by slug functionality.

Tests the missing get_by_slug method that is mentioned in acceptance criteria
but not yet implemented in the GearRepository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.gear import Gear as GearEntity
from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

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
def sample_gear() -> GearEntity:
    """Create a sample gear entity."""
    return GearEntity(
        name="Fender Deluxe Reverb",
        gear_type=GearType.AMP,
        description="Classic tube amp",
        manufacturer="Fender",
        tags=["clean", "vintage"],
        is_public=True,
    )


async def test_get_by_slug_finds_gear(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test retrieving gear by URL-friendly slug."""
    # Save gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    # Should be able to retrieve by slug (e.g., "fender-deluxe-reverb")
    retrieved = await gear_repository.get_by_slug("fender-deluxe-reverb")

    assert retrieved is not None
    assert retrieved.id == sample_gear.id
    assert retrieved.name == "Fender Deluxe Reverb"


async def test_get_by_slug_returns_none_when_not_found(
    gear_repository: SQLAlchemyGearRepository,
) -> None:
    """Test get_by_slug returns None for non-existent slug."""
    retrieved = await gear_repository.get_by_slug("non-existent-gear")
    assert retrieved is None


async def test_get_by_slug_handles_special_characters(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> None:
    """Test slug generation handles special characters correctly."""
    # Create gear with special characters
    gear = GearEntity(
        name="Boss MT-2 Metal Zone",
        gear_type=GearType.PEDAL,
        description="High-gain pedal",
    )

    await gear_repository.save(gear)
    await db_session.commit()

    # Should be able to retrieve by slug (special chars removed/normalized)
    retrieved = await gear_repository.get_by_slug("boss-mt-2-metal-zone")

    assert retrieved is not None
    assert retrieved.name == "Boss MT-2 Metal Zone"


async def test_get_by_slug_case_insensitive(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test slug lookup is case-insensitive."""
    # Save gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    # Should find with different case
    retrieved = await gear_repository.get_by_slug("FENDER-DELUXE-REVERB")

    assert retrieved is not None
    assert retrieved.id == sample_gear.id


async def test_get_by_slug_handles_duplicate_names(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> None:
    """Test slug uniqueness when multiple gear have same name."""
    # Create two gear items with the same name (different manufacturers)
    gear1 = GearEntity(
        name="Overdrive",
        gear_type=GearType.PEDAL,
        manufacturer="Boss",
    )
    gear2 = GearEntity(
        name="Overdrive",
        gear_type=GearType.PEDAL,
        manufacturer="Ibanez",
    )

    await gear_repository.save(gear1)
    await gear_repository.save(gear2)
    await db_session.commit()

    # Should be able to retrieve by manufacturer-specific slug
    boss_od = await gear_repository.get_by_slug("boss-overdrive")
    ibanez_od = await gear_repository.get_by_slug("ibanez-overdrive")

    assert boss_od is not None
    assert boss_od.manufacturer == "Boss"
    assert ibanez_od is not None
    assert ibanez_od.manufacturer == "Ibanez"


async def test_get_by_slug_with_unicode_characters(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> None:
    """Test slug generation handles unicode characters."""
    # Create gear with unicode characters
    gear = GearEntity(
        name="Röhren Amp",
        gear_type=GearType.AMP,
        description="German tube amp",
    )

    await gear_repository.save(gear)
    await db_session.commit()

    # Should be able to retrieve by normalized slug
    retrieved = await gear_repository.get_by_slug("rohren-amp")

    assert retrieved is not None
    assert retrieved.name == "Röhren Amp"
