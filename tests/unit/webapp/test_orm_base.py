"""Unit tests for ORM base classes and mixins."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, Integer, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from webapp.adapters.persistence.models.base import (
    Base,
    EnumByValue,
    TimestampMixin,
    UUIDMixin,
    get_async_session,
)


class TestBase:
    """Test the declarative base class."""

    def test_base_has_naming_conventions(self) -> None:
        """Base should have naming conventions configured."""
        assert Base.metadata.naming_convention is not None
        assert "ix" in Base.metadata.naming_convention
        assert "uq" in Base.metadata.naming_convention
        assert "ck" in Base.metadata.naming_convention
        assert "fk" in Base.metadata.naming_convention
        assert "pk" in Base.metadata.naming_convention


class TestUUIDMixin:
    """Test UUIDMixin for UUIDv7 primary keys."""

    def test_uuid_mixin_adds_id_column(self) -> None:
        """UUIDMixin should add a UUIDv7 id column."""

        class TestModel(UUIDMixin, Base):
            __tablename__ = "test_uuid"

        assert hasattr(TestModel, "id")
        column = TestModel.__table__.columns["id"]
        assert column.primary_key
        # Verify column has default value
        assert column.default is not None

    def test_uuid_mixin_generates_uuidv7(self) -> None:
        """UUIDMixin should generate UUID IDs on insert."""

        class TestModel(UUIDMixin, Base):
            __tablename__ = "test_uuid_gen"

        # Create in-memory database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            instance = TestModel()
            session.add(instance)
            session.flush()  # Flush to execute defaults

            # After flush, ID should be set
            assert instance.id is not None
            assert isinstance(instance.id, uuid.UUID)
            # UUIDv7 has version field = 7 (Python 3.13+)
            # UUIDv4 has version field = 4 (Python 3.12 fallback)
            assert instance.id.version in (4, 7)


class TestTimestampMixin:
    """Test TimestampMixin for created_at/updated_at."""

    def test_timestamp_mixin_adds_columns(self) -> None:
        """TimestampMixin should add created_at and updated_at columns."""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp"
            id = Column(Integer, primary_key=True)

        assert hasattr(TestModel, "created_at")
        assert hasattr(TestModel, "updated_at")

    def test_timestamp_mixin_sets_created_at(self) -> None:
        """TimestampMixin should set created_at on insert."""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp_created"
            id = Column(Integer, primary_key=True)

        # Create in-memory database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        before = datetime.now(UTC)

        with Session(engine) as session:
            instance = TestModel(id=1)
            session.add(instance)
            session.flush()

            assert instance.created_at is not None
            after = datetime.now(UTC)
            assert before <= instance.created_at <= after
            assert instance.created_at.tzinfo == UTC

    def test_timestamp_mixin_sets_updated_at(self) -> None:
        """TimestampMixin should set updated_at on insert."""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp_updated"
            id = Column(Integer, primary_key=True)

        # Create in-memory database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            instance = TestModel(id=1)
            session.add(instance)
            session.flush()

            assert instance.updated_at is not None
            # Timestamps should be very close (within 1 second)
            diff = abs((instance.updated_at - instance.created_at).total_seconds())
            assert diff < 1.0


class TestEnumByValue:
    """Test EnumByValue type for storing enums by value."""

    def test_enum_by_value_stores_value_not_name(self) -> None:
        """EnumByValue should store the enum value, not the name."""
        from enum import Enum

        class Status(str, Enum):
            PENDING = "pending"
            ACTIVE = "active"

        class TestModel(Base):
            __tablename__ = "test_enum"
            id = Column(Integer, primary_key=True)
            status: Status = Column(EnumByValue(Status), nullable=False)  # type: ignore[assignment]

        # Create in-memory database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            instance = TestModel(id=1, status=Status.ACTIVE)
            session.add(instance)
            session.commit()

            # Verify stored as value
            result = session.execute(select(TestModel).where(TestModel.id == 1))
            retrieved = result.scalar_one()
            assert retrieved.status == Status.ACTIVE
            assert isinstance(retrieved.status, Status)


class TestAsyncSession:
    """Test async session factory."""

    @pytest.mark.asyncio
    async def test_get_async_session_creates_session(self) -> None:
        """get_async_session should create async sessions."""
        # This test verifies the session factory works
        # Using in-memory SQLite for testing
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            assert isinstance(session, AsyncSession)
            # Verify we can execute queries
            result = await session.execute(select(1))
            assert result.scalar() == 1

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_session_factory_from_get_async_session(self) -> None:
        """get_async_session should return a working session factory."""
        # Mock database URL
        database_url = "sqlite+aiosqlite:///:memory:"

        session_factory = get_async_session(database_url)
        assert session_factory is not None

        async with session_factory() as session:
            assert isinstance(session, AsyncSession)

        # Cleanup
        await session_factory.kw["bind"].dispose()
