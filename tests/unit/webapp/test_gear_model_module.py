"""Unit tests for GearModel ORM model in dedicated module.

This test verifies that GearModel exists in its own module at
apps/webapp/src/webapp/adapters/persistence/models/gear_model.py
as specified in the task requirements.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import ModelSize, Platform
from webapp.adapters.persistence.models.base import Base


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
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


class TestGearModelModule:
    """Tests for GearModel module structure."""

    def test_gear_model_module_exists(self) -> None:
        """Test that gear_model module exists at expected location."""
        # This import will fail if the module doesn't exist
        from webapp.adapters.persistence.models.gear_model import GearModel

        assert GearModel is not None

    def test_gear_model_has_table_name(self) -> None:
        """Test that GearModel has correct table name."""
        from webapp.adapters.persistence.models.gear_model import GearModel

        assert GearModel.__tablename__ == "gear_models"

    def test_gear_model_has_required_fields(self) -> None:
        """Test that GearModel has all required fields."""
        from webapp.adapters.persistence.models.gear_model import GearModel

        # Required fields from existing implementation
        required_fields = {
            "id",
            "gear_id",
            "platform",
            "size",
            "file_path",
            "download_url",
            "download_status",
            "file_hash",
        }

        model_fields = set(GearModel.__annotations__.keys())

        assert required_fields.issubset(
            model_fields
        ), f"Missing required fields. Expected at least {required_fields}, got {model_fields}"

    async def test_gear_model_creation(self, session: AsyncSession) -> None:
        """Test creating a GearModel instance."""
        from sqlalchemy import select

        # Create parent gear first
        from core.domain.value_objects.signal_chain_enums import GearType
        from webapp.adapters.persistence.models.gear import Gear
        from webapp.adapters.persistence.models.gear_model import GearModel

        gear = Gear(
            name="Test Amp",
            gear_type=GearType.AMP,
        )
        session.add(gear)
        await session.flush()

        # Create gear model
        model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
            download_url="https://example.com/model.nam",
            download_status=DownloadStatus.PENDING,
        )

        session.add(model)
        await session.commit()

        # Verify
        result = await session.execute(select(GearModel).where(GearModel.gear_id == gear.id))
        saved_model = result.scalar_one()

        assert saved_model.platform == Platform.NAM
        assert saved_model.size == ModelSize.STANDARD
        assert saved_model.download_status == DownloadStatus.PENDING

    async def test_gear_model_platform_enum_storage(self, session: AsyncSession) -> None:
        """Test that platform enum is stored by value."""
        from sqlalchemy import select

        from core.domain.value_objects.signal_chain_enums import GearType
        from webapp.adapters.persistence.models.gear import Gear
        from webapp.adapters.persistence.models.gear_model import GearModel

        gear = Gear(name="Test", gear_type=GearType.AMP)
        session.add(gear)
        await session.flush()

        model = GearModel(
            gear_id=gear.id,
            platform=Platform.AIDA_X,
            size=ModelSize.LITE,
            download_status=DownloadStatus.PENDING,
        )

        session.add(model)
        await session.commit()

        # Verify enum storage
        result = await session.execute(select(GearModel).where(GearModel.gear_id == gear.id))
        saved_model = result.scalar_one()

        assert saved_model.platform == Platform.AIDA_X
        assert saved_model.platform.value == "aida_x"

    async def test_gear_model_nullable_fields(self, session: AsyncSession) -> None:
        """Test that optional fields can be null."""
        from sqlalchemy import select

        from core.domain.value_objects.signal_chain_enums import GearType
        from webapp.adapters.persistence.models.gear import Gear
        from webapp.adapters.persistence.models.gear_model import GearModel

        gear = Gear(name="Test", gear_type=GearType.AMP)
        session.add(gear)
        await session.flush()

        # Create model with only required fields
        model = GearModel(
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
            download_status=DownloadStatus.PENDING,
        )

        session.add(model)
        await session.commit()

        # Verify nullable fields
        result = await session.execute(select(GearModel).where(GearModel.gear_id == gear.id))
        saved_model = result.scalar_one()

        assert saved_model.file_path is None
        assert saved_model.download_url is None
        assert saved_model.file_hash is None

    async def test_gear_model_has_indexes(self, session: AsyncSession) -> None:
        """Test that GearModel has indexes for common query patterns."""
        from webapp.adapters.persistence.models.gear_model import GearModel

        # Verify indexes exist in model definition
        gear_model_table = GearModel.__table__

        index_names = {index.name for index in gear_model_table.indexes}

        # Should have indexes for gear_id and platform
        assert "ix_gearmodel_gear_id" in index_names
        assert "ix_gearmodel_platform" in index_names
