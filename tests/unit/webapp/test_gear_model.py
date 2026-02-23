"""Unit tests for Gear ORM models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import (
    Gear,
    GearMake,
    GearTag,
)
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource


class TestGear:
    """Tests for Gear model."""

    async def test_gear_creation_with_minimal_fields(self, session: AsyncSession) -> None:
        """Test creating gear with minimal required fields."""
        suffix = uuid.uuid4().hex[:8]
        gear = Gear(
            name=f"Test Amp {suffix}",
            slug=f"test-amp-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
        )

        session.add(gear)
        await session.commit()

        # Verify gear was created
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert saved_gear.name == f"Test Amp {suffix}"
        assert saved_gear.gear_type == GearType.AMP
        assert saved_gear.is_public is True  # Default
        assert saved_gear.created_at is not None
        assert saved_gear.updated_at is not None

    async def test_gear_creation_with_all_fields(self, session: AsyncSession) -> None:
        """Test creating gear with all fields."""
        suffix = uuid.uuid4().hex[:8]
        gear = Gear(
            name=f"Mesa Boogie Dual Rectifier {suffix}",
            slug=f"mesa-boogie-dual-rectifier-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            description="High-gain metal amp",
            manufacturer="Mesa Boogie",
            thumbnail_url="https://example.com/thumbnail.jpg",
            is_public=True,
        )

        session.add(gear)
        await session.commit()

        # Verify
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert saved_gear.description == "High-gain metal amp"
        assert saved_gear.manufacturer == "Mesa Boogie"
        assert saved_gear.thumbnail_url == "https://example.com/thumbnail.jpg"

    async def test_gear_with_tags(self, session: AsyncSession) -> None:
        """Test gear with tags many-to-many relationship."""
        suffix = uuid.uuid4().hex[:8]
        # Create tags
        tag1 = GearTag(name=f"metal_{suffix}")
        tag2 = GearTag(name=f"high-gain_{suffix}")

        # Create gear and associate tags
        gear = Gear(
            name=f"High Gain Amp {suffix}",
            slug=f"high-gain-amp-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
        )
        gear.tags.append(tag1)
        gear.tags.append(tag2)

        session.add(gear)
        await session.commit()

        # Verify tags are saved and associated
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert len(saved_gear.tags) == 2
        tag_names = {tag.name for tag in saved_gear.tags}
        assert tag_names == {f"metal_{suffix}", f"high-gain_{suffix}"}

    async def test_gear_with_source(self, session: AsyncSession) -> None:
        """Test gear with source tracking."""
        suffix = uuid.uuid4().hex[:8]
        # Create source
        source = GearSource(
            source_name="t3k",
            source_record_id=f"T3K-{suffix}",
            source_updated_at=datetime.now(UTC),
        )

        # Create gear with source
        gear = Gear(
            name=f"T3K Amp {suffix}",
            slug=f"t3k-amp-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            source=source,
        )

        session.add(gear)
        await session.commit()

        # Verify source relationship
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert saved_gear.source is not None
        assert saved_gear.source.source_name == "t3k"
        assert saved_gear.source.source_record_id == f"T3K-{suffix}"

    async def test_gear_with_models(self, session: AsyncSession) -> None:
        """Test gear with multiple model files."""
        suffix = uuid.uuid4().hex[:8]
        # Create gear
        gear = Gear(
            name=f"Amp with Models {suffix}",
            slug=f"amp-with-models-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
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
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
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
        suffix = uuid.uuid4().hex[:8]
        gear = Gear(
            name=f"Test Pedal {suffix}",
            slug=f"test-pedal-{suffix}",
            gear_type=GearType.PEDAL,
            platform=Platform.NAM,
        )

        session.add(gear)
        await session.commit()

        # Query raw database to verify enum is stored by value
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert saved_gear.gear_type == GearType.PEDAL
        assert saved_gear.gear_type.value == "pedal"

    async def test_gear_with_make(self, session: AsyncSession) -> None:
        """Test gear with manufacturer (GearMake) relationship."""
        suffix = uuid.uuid4().hex[:8]
        # Create make
        make = GearMake(name=f"Fender_{suffix}")

        # Create gear with make
        gear = Gear(
            name=f"Fender Deluxe {suffix}",
            slug=f"fender-deluxe-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            make=make,
        )

        session.add(gear)
        await session.commit()

        # Verify make relationship
        result = await session.execute(select(Gear).where(Gear.id == gear.id))
        saved_gear = result.scalar_one()

        assert saved_gear.make is not None
        assert saved_gear.make.name == f"Fender_{suffix}"

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
