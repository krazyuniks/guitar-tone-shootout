"""Integration tests for T16: Gear Repository - Get by slug functionality.

Tests the missing get_by_slug method that is mentioned in acceptance criteria
but not yet implemented in the GearRepository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


import pytest

from gts.domain.entities.gear import Gear as GearEntity
from gts.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)


@pytest.fixture
def gear_repository(db_session: AsyncSession) -> SQLAlchemyGearRepository:
    """Create a GearRepository instance."""
    return SQLAlchemyGearRepository(db_session)


@pytest.fixture
def sample_gear() -> GearEntity:
    """Create a sample gear entity with a unique name to avoid T3K sync collisions."""
    return GearEntity(
        name="TestMfr T16 Fixture Amp",
        gear_type=GearType.AMP,
        description="Classic tube amp",
        manufacturer="TestMfr",
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

    retrieved = await gear_repository.get_by_slug("testmfr-t16-fixture-amp")

    assert retrieved is not None
    assert retrieved.id == sample_gear.id
    assert retrieved.name == "TestMfr T16 Fixture Amp"


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
    gear = GearEntity(
        name="T16 Test-Pedal XZ-99",
        gear_type=GearType.PEDAL,
        description="High-gain pedal",
    )

    await gear_repository.save(gear)
    await db_session.commit()

    retrieved = await gear_repository.get_by_slug("t16-test-pedal-xz-99")

    assert retrieved is not None
    assert retrieved.name == "T16 Test-Pedal XZ-99"


async def test_get_by_slug_case_insensitive(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test slug lookup is case-insensitive."""
    # Save gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    retrieved = await gear_repository.get_by_slug("TESTMFR-T16-FIXTURE-AMP")

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
