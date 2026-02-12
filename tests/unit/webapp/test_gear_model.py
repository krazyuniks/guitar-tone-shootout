"""Unit tests for Gear ORM models."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import (
    Gear,
    GearMake,
    GearTag,
)
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # Create in-memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory and session
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


class TestGear:
    """Tests for Gear model."""

    async def test_gear_creation_with_minimal_fields(self, session: AsyncSession) -> None:
        """Test creating gear with minimal required fields."""
        gear = Gear(
            name="Test Amp",
            gear_type=GearType.AMP,
        )

        session.add(gear)
        await session.commit()

        # Verify gear was created
        result = await session.execute(select(Gear).where(Gear.name == "Test Amp"))
        saved_gear = result.scalar_one()

        assert saved_gear.name == "Test Amp"
        assert saved_gear.gear_type == GearType.AMP
        assert saved_gear.is_public is True  # Default
        assert saved_gear.created_at is not None
        assert saved_gear.updated_at is not None

    async def test_gear_creation_with_all_fields(self, session: AsyncSession) -> None:
        """Test creating gear with all fields."""
        gear = Gear(
            name="Mesa Boogie Dual Rectifier",
            gear_type=GearType.AMP,
            description="High-gain metal amp",
            manufacturer="Mesa Boogie",
            thumbnail_url="https://example.com/thumbnail.jpg",
            is_public=True,
        )

        session.add(gear)
        await session.commit()

        # Verify
        result = await session.execute(
            select(Gear).where(Gear.name == "Mesa Boogie Dual Rectifier")
        )
        saved_gear = result.scalar_one()

        assert saved_gear.description == "High-gain metal amp"
        assert saved_gear.manufacturer == "Mesa Boogie"
        assert saved_gear.thumbnail_url == "https://example.com/thumbnail.jpg"

    async def test_gear_with_tags(self, session: AsyncSession) -> None:
        """Test gear with tags many-to-many relationship."""
        # Create tags
        tag1 = GearTag(name="metal")
        tag2 = GearTag(name="high-gain")

        # Create gear and associate tags
        gear = Gear(
            name="High Gain Amp",
            gear_type=GearType.AMP,
        )
        gear.tags.append(tag1)
        gear.tags.append(tag2)

        session.add(gear)
        await session.commit()

        # Verify tags are saved and associated
        result = await session.execute(select(Gear).where(Gear.name == "High Gain Amp"))
        saved_gear = result.scalar_one()

        assert len(saved_gear.tags) == 2
        tag_names = {tag.name for tag in saved_gear.tags}
        assert tag_names == {"metal", "high-gain"}

    async def test_gear_with_source(self, session: AsyncSession) -> None:
        """Test gear with source tracking."""
        # Create source
        source = GearSource(
            source_name="t3k",
            source_record_id="T3K-12345",
            source_updated_at=datetime.now(UTC),
        )

        # Create gear with source
        gear = Gear(
            name="T3K Amp",
            gear_type=GearType.AMP,
            source=source,
        )

        session.add(gear)
        await session.commit()

        # Verify source relationship
        result = await session.execute(select(Gear).where(Gear.name == "T3K Amp"))
        saved_gear = result.scalar_one()

        assert saved_gear.source is not None
        assert saved_gear.source.source_name == "t3k"
        assert saved_gear.source.source_record_id == "T3K-12345"

    async def test_gear_with_models(self, session: AsyncSession) -> None:
        """Test gear with multiple model files."""
        # Create gear
        gear = Gear(
            name="Amp with Models",
            gear_type=GearType.AMP,
        )

        # Create models
        model1 = GearModel(
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
            download_url="https://example.com/model1.nam",
            download_status=DownloadStatus.PENDING,
        )
        model2 = GearModel(
            platform=Platform.NAM,
            size=ModelSize.LITE,
            download_url="https://example.com/model2.nam",
            download_status=DownloadStatus.COMPLETED,
            file_path="/models/model2.nam",
            file_hash="abc123",
        )

        gear.models.append(model1)
        gear.models.append(model2)

        session.add(gear)
        await session.commit()

        # Verify models are saved and associated
        result = await session.execute(select(Gear).where(Gear.name == "Amp with Models"))
        saved_gear = result.scalar_one()

        assert len(saved_gear.models) == 2

        # Check standard model
        standard = next(m for m in saved_gear.models if m.size == ModelSize.STANDARD)
        assert standard.platform == Platform.NAM
        assert standard.download_status == DownloadStatus.PENDING

        # Check lite model
        lite = next(m for m in saved_gear.models if m.size == ModelSize.LITE)
        assert lite.file_path == "/models/model2.nam"
        assert lite.file_hash == "abc123"

    async def test_gear_type_enum_storage(self, session: AsyncSession) -> None:
        """Test that gear_type enum is stored by value."""
        gear = Gear(
            name="Test Pedal",
            gear_type=GearType.PEDAL,
        )

        session.add(gear)
        await session.commit()

        # Query raw database to verify enum is stored by value
        result = await session.execute(select(Gear).where(Gear.name == "Test Pedal"))
        saved_gear = result.scalar_one()

        assert saved_gear.gear_type == GearType.PEDAL
        assert saved_gear.gear_type.value == "pedal"

    async def test_gear_with_make(self, session: AsyncSession) -> None:
        """Test gear with manufacturer (GearMake) relationship."""
        # Create make
        make = GearMake(name="Fender")

        # Create gear with make
        gear = Gear(
            name="Fender Deluxe",
            gear_type=GearType.AMP,
            make=make,
        )

        session.add(gear)
        await session.commit()

        # Verify make relationship
        result = await session.execute(select(Gear).where(Gear.name == "Fender Deluxe"))
        saved_gear = result.scalar_one()

        assert saved_gear.make is not None
        assert saved_gear.make.name == "Fender"

    async def test_indexes_exist(self, session: AsyncSession) -> None:
        """Test that indexes are created for common query patterns."""
        from sqlalchemy import Table

        # This test verifies the model structure has index configurations
        # Actual index creation is verified by the database migration

        # Check gear_type index is defined
        gear_table: Table = Gear.__table__  # type: ignore[assignment]
        assert any(index.name == "ix_gear_type" for index in gear_table.indexes)

        # Check platform index on gear_models is defined
        gear_model_table: Table = GearModel.__table__  # type: ignore[assignment]
        assert any(index.name == "ix_gearmodel_platform" for index in gear_model_table.indexes)
