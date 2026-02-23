"""Integration tests for GearRepository implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


from datetime import UTC

import pytest

from gts.domain.entities.gear import Gear as GearEntity
from gts.domain.entities.gear import GearModel as GearModelVO
from gts.domain.entities.gear import GearSource as GearSourceVO
from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.signal_chain_enums import (
    GearType,
    ModelSize,
    Platform,
)
from webapp.adapters.persistence.repositories.gear_repository import SQLAlchemyGearRepository


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


@pytest.fixture
def sample_gear_with_source() -> GearEntity:
    """Create a sample gear entity with source."""
    from datetime import datetime

    return GearEntity(
        name="Marshall JCM800",
        gear_type=GearType.AMP,
        description="High-gain amp",
        manufacturer="Marshall",
        tags=["high-gain", "metal"],
        source=GearSourceVO(
            source_name="t3k",
            source_record_id="123",
            source_updated_at=datetime.now(UTC),
        ),
        is_public=True,
    )


@pytest.fixture
def sample_gear_with_models() -> GearEntity:
    """Create a sample gear entity with model files."""
    gear = GearEntity(
        name="Boss DS-1",
        gear_type=GearType.PEDAL,
        description="Distortion pedal",
        manufacturer="Boss",
        tags=["distortion"],
        is_public=True,
    )

    # Add model files
    from gts.domain.entities.base import new_id

    model1 = GearModelVO(
        id=new_id(),
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        download_url="https://example.com/model1.nam",
        download_status=DownloadStatus.PENDING,
    )
    model2 = GearModelVO(
        id=new_id(),
        platform=Platform.NAM,
        size=ModelSize.LITE,
        download_url="https://example.com/model2.nam",
        download_status=DownloadStatus.PENDING,
    )
    gear.models = [model1, model2]

    return gear


async def test_save_and_get_by_id(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test saving gear and retrieving by ID."""
    # Save gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    # Get by ID
    retrieved = await gear_repository.get_by_id(sample_gear.id)

    assert retrieved is not None
    assert retrieved.id == sample_gear.id
    assert retrieved.name == "Fender Deluxe Reverb"
    assert retrieved.gear_type == GearType.AMP
    assert retrieved.description == "Classic tube amp"
    assert retrieved.manufacturer == "Fender"
    assert set(retrieved.tags) == {"clean", "vintage"}
    assert retrieved.is_public is True


async def test_save_gear_with_source(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test saving gear with source tracking."""
    # Save gear with source
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Get by ID
    retrieved = await gear_repository.get_by_id(sample_gear_with_source.id)

    assert retrieved is not None
    assert retrieved.source is not None
    assert retrieved.source.source_name == "t3k"
    assert retrieved.source.source_record_id == "123"


async def test_get_by_source(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test retrieving gear by source identifier."""
    # Save gear
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Get by source
    retrieved = await gear_repository.get_by_source("t3k", "123")

    assert retrieved is not None
    assert retrieved.id == sample_gear_with_source.id
    assert retrieved.name == "Marshall JCM800"


async def test_save_gear_with_models(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear_with_models: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test saving gear with model files."""
    # Save gear with models
    await gear_repository.save(sample_gear_with_models)
    await db_session.commit()

    # Get by ID
    retrieved = await gear_repository.get_by_id(sample_gear_with_models.id)

    assert retrieved is not None
    assert len(retrieved.models) == 2
    assert all(m.platform == Platform.NAM for m in retrieved.models)
    assert {m.size for m in retrieved.models} == {ModelSize.STANDARD, ModelSize.LITE}


async def test_search_by_gear_type(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test searching gear by type."""
    # Save multiple gear items
    pedal = GearEntity(
        name="Test Pedal",
        gear_type=GearType.PEDAL,
        description="Test pedal",
    )

    await gear_repository.save(sample_gear)
    await gear_repository.save(pedal)
    await db_session.commit()

    # Search for amps
    results = await gear_repository.search(gear_type=GearType.AMP)

    assert len(results) == 1
    assert results[0].gear_type == GearType.AMP
    assert results[0].name == "Fender Deluxe Reverb"


async def test_search_by_manufacturer(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test searching gear by manufacturer."""
    # Save multiple gear items
    await gear_repository.save(sample_gear)
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Search for Fender
    results = await gear_repository.search(manufacturer="Fender")

    assert len(results) == 1
    assert results[0].manufacturer == "Fender"


async def test_search_by_query(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test text search on name and description."""
    # Save multiple gear items
    await gear_repository.save(sample_gear)
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Search for "Deluxe"
    results = await gear_repository.search(query="Deluxe")

    assert len(results) == 1
    assert "Deluxe" in results[0].name


async def test_search_by_tags(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test searching gear by tags (AND logic)."""
    # Save gear items
    await gear_repository.save(sample_gear)
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Search for "vintage" tag
    results = await gear_repository.search(tags=["vintage"])

    assert len(results) == 1
    assert results[0].has_tag("vintage")

    # Search for multiple tags (AND)
    results = await gear_repository.search(tags=["high-gain", "metal"])

    assert len(results) == 1
    assert results[0].has_tag("high-gain")
    assert results[0].has_tag("metal")


async def test_search_with_pagination(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> None:
    """Test search with limit and offset."""
    # Create multiple gear items
    for i in range(5):
        gear = GearEntity(
            name=f"Gear {i}",
            gear_type=GearType.AMP,
        )
        await gear_repository.save(gear)
    await db_session.commit()

    # Test limit
    results = await gear_repository.search(limit=2)
    assert len(results) == 2

    # Test offset
    results_page1 = await gear_repository.search(limit=2, offset=0)
    results_page2 = await gear_repository.search(limit=2, offset=2)

    assert len(results_page1) == 2
    assert len(results_page2) == 2
    assert results_page1[0].id != results_page2[0].id


async def test_count(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    sample_gear_with_source: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test counting gear with filters."""
    # Save gear items
    await gear_repository.save(sample_gear)
    await gear_repository.save(sample_gear_with_source)
    await db_session.commit()

    # Count all
    total = await gear_repository.count()
    assert total == 2

    # Count by type
    amp_count = await gear_repository.count(gear_type=GearType.AMP)
    assert amp_count == 2

    # Count by manufacturer
    fender_count = await gear_repository.count(manufacturer="Fender")
    assert fender_count == 1


async def test_update_gear(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test updating existing gear."""
    # Save initial gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    # Update gear
    from dataclasses import replace

    updated_gear = replace(
        sample_gear,
        name="Updated Name",
        description="Updated description",
    )

    await gear_repository.save(updated_gear)
    await db_session.commit()

    # Retrieve and verify
    retrieved = await gear_repository.get_by_id(sample_gear.id)

    assert retrieved is not None
    assert retrieved.name == "Updated Name"
    assert retrieved.description == "Updated description"


async def test_delete_gear(
    gear_repository: SQLAlchemyGearRepository,
    sample_gear: GearEntity,
    db_session: AsyncSession,
) -> None:
    """Test deleting gear."""
    # Save gear
    await gear_repository.save(sample_gear)
    await db_session.commit()

    # Delete gear
    await gear_repository.delete(sample_gear.id)
    await db_session.commit()

    # Verify deleted
    retrieved = await gear_repository.get_by_id(sample_gear.id)
    assert retrieved is None
