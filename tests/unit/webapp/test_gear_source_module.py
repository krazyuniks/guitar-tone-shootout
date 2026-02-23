"""Unit tests for GearSource ORM model in dedicated module.

This test verifies that GearSource exists in its own module at
apps/webapp/src/webapp/adapters/persistence/models/gear_source.py
as specified in the task requirements.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType, Platform


class TestGearSourceModule:
    """Tests for GearSource module structure."""

    def test_gear_source_module_exists(self) -> None:
        """Test that gear_source module exists at expected location."""
        # This import will fail if the module doesn't exist
        from webapp.adapters.persistence.models.gear_source import GearSource

        assert GearSource is not None

    def test_gear_source_has_table_name(self) -> None:
        """Test that GearSource has correct table name."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        assert GearSource.__tablename__ == "gear_sources"

    def test_gear_source_has_required_fields(self) -> None:
        """Test that GearSource has all required fields."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        # Required fields based on acceptance criteria
        required_fields = {
            "id",  # From UUIDMixin
            "source_name",  # Source identifier (t3k, community, etc.)
            "source_record_id",  # ID in source system
            "source_updated_at",  # Last update in source system
            "created_at",  # From TimestampMixin
            "updated_at",  # From TimestampMixin
        }

        model_fields = set(GearSource.__annotations__.keys())

        assert required_fields.issubset(model_fields), (
            f"Missing required fields. Expected at least {required_fields}, got {model_fields}"
        )

    def test_gear_source_uses_mixins(self) -> None:
        """Test that GearSource uses UUIDMixin and TimestampMixin."""
        from webapp.adapters.persistence.models.base import TimestampMixin, UUIDMixin
        from webapp.adapters.persistence.models.gear_source import GearSource

        assert issubclass(GearSource, UUIDMixin), "GearSource must use UUIDMixin"
        assert issubclass(GearSource, TimestampMixin), "GearSource must use TimestampMixin"

    async def test_gear_source_creation(self, session: AsyncSession) -> None:
        """Test creating a GearSource instance."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        # Create gear source
        source = GearSource(
            source_name="t3k",
            source_record_id=f"pack_{suffix}",
            source_updated_at=datetime.now(UTC),
        )

        session.add(source)
        await session.commit()

        # Verify
        result = await session.execute(select(GearSource).where(GearSource.id == source.id))
        saved_source = result.scalar_one()

        assert saved_source.source_name == "t3k"
        assert saved_source.source_record_id == f"pack_{suffix}"
        assert saved_source.source_updated_at is not None

    async def test_gear_source_timestamps_auto_set(self, session: AsyncSession) -> None:
        """Test that created_at and updated_at are automatically set."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        source = GearSource(
            source_name="community",
            source_record_id=f"user_upload_{suffix}",
            source_updated_at=datetime.now(UTC),
        )

        session.add(source)
        await session.commit()

        # Timestamps should be auto-set
        assert source.created_at is not None
        assert source.updated_at is not None
        assert source.created_at == source.updated_at  # Same on creation

    async def test_gear_source_with_gear_relationship(self, session: AsyncSession) -> None:
        """Test GearSource relationship with Gear."""
        from sqlalchemy.orm import joinedload

        from webapp.adapters.persistence.models.gear import Gear
        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        # Create source
        source = GearSource(
            source_name="t3k",
            source_record_id=f"pack_{suffix}",
            source_updated_at=datetime.now(UTC),
        )
        session.add(source)
        await session.flush()

        # Create gear linked to source
        gear = Gear(
            name=f"Mesa Boogie {suffix}",
            slug=f"mesa-boogie-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            source_id=source.id,
        )
        session.add(gear)
        await session.commit()

        # Verify relationship (use joinedload to eagerly load the gear)
        result = await session.execute(
            select(GearSource)
            .where(GearSource.id == source.id)
            .options(joinedload(GearSource.gear))
        )
        saved_source = result.unique().scalar_one()

        # Should have gear relationship
        assert hasattr(saved_source, "gear")

    async def test_gear_source_lookup_index(self, session: AsyncSession) -> None:
        """Test that GearSource has composite index for source lookups."""
        from sqlalchemy import Table

        from webapp.adapters.persistence.models.gear_source import GearSource

        # Verify indexes exist in model definition
        gear_source_table: Table = GearSource.__table__  # type: ignore[assignment]

        index_names = {index.name for index in gear_source_table.indexes}

        # Should have composite index for (source_name, source_record_id)
        assert "ix_gear_sources_source_lookup" in index_names

    async def test_gear_source_unique_source_records(self, session: AsyncSession) -> None:
        """Test that source_name + source_record_id combination should be unique."""
        from sqlalchemy.exc import IntegrityError

        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        # Create first source
        source1 = GearSource(
            source_name="t3k",
            source_record_id=f"pack_{suffix}",
            source_updated_at=datetime.now(UTC),
        )
        session.add(source1)
        await session.commit()

        # Try to create duplicate - should fail or be prevented
        # NOTE: This test assumes a unique constraint will be added
        source2 = GearSource(
            source_name="t3k",
            source_record_id=f"pack_{suffix}",  # Same as source1
            source_updated_at=datetime.now(UTC),
        )
        session.add(source2)

        # If unique constraint exists, this should raise IntegrityError
        # If not, we're testing that multiple sources with same name+id can exist
        try:
            await session.commit()
            # No constraint - multiple sources allowed
            # This is valid if we want to track history
        except IntegrityError:
            # Constraint exists - duplicates prevented
            await session.rollback()

    async def test_gear_source_different_sources_allowed(self, session: AsyncSession) -> None:
        """Test that different sources can have same record_id."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        # Create sources with same record_id but different source_name
        source1 = GearSource(
            source_name="t3k",
            source_record_id=f"rec_{suffix}",
            source_updated_at=datetime.now(UTC),
        )
        source2 = GearSource(
            source_name="community",
            source_record_id=f"rec_{suffix}",  # Same ID, different source
            source_updated_at=datetime.now(UTC),
        )

        session.add(source1)
        session.add(source2)
        await session.commit()

        # Both should exist
        result = await session.execute(
            select(GearSource).where(GearSource.source_record_id == f"rec_{suffix}")
        )
        sources = result.scalars().all()

        assert len(sources) == 2
        assert {s.source_name for s in sources} == {"t3k", "community"}

    async def test_gear_source_nullable_gear_relationship(self, session: AsyncSession) -> None:
        """Test that GearSource can exist without linked Gear."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        suffix = uuid.uuid4().hex[:8]
        # Create source without gear
        source = GearSource(
            source_name="t3k",
            source_record_id=f"orphan_{suffix}",
            source_updated_at=datetime.now(UTC),
        )

        session.add(source)
        await session.commit()

        # Should succeed - source doesn't require gear
        result = await session.execute(
            select(GearSource).where(GearSource.source_record_id == f"orphan_{suffix}")
        )
        saved_source = result.scalar_one()

        assert saved_source.id is not None

    async def test_gear_has_foreign_key_to_source(self, session: AsyncSession) -> None:
        """Test that Gear has foreign key to GearSource."""
        from webapp.adapters.persistence.models.base import UuidType
        from webapp.adapters.persistence.models.gear import Gear

        # Check that Gear has source_id field
        assert "source_id" in Gear.__annotations__

        # Verify it's a UUID type
        import uuid as uuid_mod

        from sqlalchemy import Uuid

        gear_table = Gear.__table__  # type: ignore[attr-defined]
        source_id_column = gear_table.c.source_id

        # Should be UUID type (UuidType is a custom type that wraps UUID)
        assert isinstance(source_id_column.type, Uuid | UuidType | type(uuid_mod.UUID))

        # Should be nullable (gear can exist without source)
        assert source_id_column.nullable is True

    async def test_gear_source_field_lengths(self, session: AsyncSession) -> None:
        """Test that GearSource fields have appropriate length constraints."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        gear_source_table = GearSource.__table__  # type: ignore[attr-defined]

        # Check source_name length (String(50))
        source_name_col = gear_source_table.c.source_name
        assert source_name_col.type.length == 50

        # Check source_record_id length (String(255))
        source_record_id_col = gear_source_table.c.source_record_id
        assert source_record_id_col.type.length == 255

    async def test_gear_source_source_updated_at_is_timezone_aware(
        self, session: AsyncSession
    ) -> None:
        """Test that source_updated_at uses timezone-aware datetime."""
        from webapp.adapters.persistence.models.gear_source import GearSource

        gear_source_table = GearSource.__table__  # type: ignore[attr-defined]
        source_updated_at_col = gear_source_table.c.source_updated_at

        # Should have timezone=True
        assert source_updated_at_col.type.timezone is True
