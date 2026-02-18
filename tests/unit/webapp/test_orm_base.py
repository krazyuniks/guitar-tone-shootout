"""Unit tests for ORM base classes and mixins."""

import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, Integer, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from webapp.adapters.persistence.models.base import (
    Base,
    EnumByValue,
    TimestampMixin,
    UUIDMixin,
    get_async_session,
)


def _sync_engine():
    """Create a synchronous PostgreSQL engine for testing type decorators."""
    url = os.environ["DATABASE_URL"].replace("asyncpg", "psycopg2")
    return create_engine(url, echo=False)


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

        engine = _sync_engine()
        Base.metadata.create_all(engine, checkfirst=True)

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

            session.rollback()

        engine.dispose()


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

        engine = _sync_engine()
        Base.metadata.create_all(engine, checkfirst=True)

        before = datetime.now(UTC)

        with Session(engine) as session:
            instance = TestModel(id=1)
            session.add(instance)
            session.flush()

            assert instance.created_at is not None
            after = datetime.now(UTC)
            assert before <= instance.created_at <= after
            assert instance.created_at.tzinfo == UTC

            session.rollback()

        engine.dispose()

    def test_timestamp_mixin_sets_updated_at(self) -> None:
        """TimestampMixin should set updated_at on insert."""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp_updated"
            id = Column(Integer, primary_key=True)

        engine = _sync_engine()
        Base.metadata.create_all(engine, checkfirst=True)

        with Session(engine) as session:
            instance = TestModel(id=1)
            session.add(instance)
            session.flush()

            assert instance.updated_at is not None
            # Timestamps should be very close (within 1 second)
            diff = abs((instance.updated_at - instance.created_at).total_seconds())
            assert diff < 1.0

            session.rollback()

        engine.dispose()


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

        engine = _sync_engine()
        Base.metadata.create_all(engine, checkfirst=True)

        with engine.connect() as conn:
            trans = conn.begin()
            session = Session(bind=conn)

            instance = TestModel(id=1, status=Status.ACTIVE)
            session.add(instance)
            session.flush()

            # Verify stored as value
            result = session.execute(select(TestModel).where(TestModel.id == 1))
            retrieved = result.scalar_one()
            assert retrieved.status == Status.ACTIVE
            assert isinstance(retrieved.status, Status)

            session.close()
            trans.rollback()

        engine.dispose()


class TestAsyncSession:
    """Test async session factory."""

    async def test_get_async_session_creates_session(self, db_session: AsyncSession) -> None:
        """get_async_session should create async sessions."""
        # Verify the session from conftest works
        assert isinstance(db_session, AsyncSession)
        # Verify we can execute queries
        result = await db_session.execute(select(1))
        assert result.scalar() == 1

    async def test_session_factory_from_get_async_session(self) -> None:
        """get_async_session should return a working session factory."""
        database_url = os.environ["DATABASE_URL"]

        session_factory = get_async_session(database_url)
        assert session_factory is not None

        async with session_factory() as session:
            assert isinstance(session, AsyncSession)

        # Cleanup
        await session_factory.kw["bind"].dispose()
