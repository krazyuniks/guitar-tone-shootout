"""SQLAlchemy base classes, mixins, and utilities for ORM models."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import DateTime, MetaData, TypeDecorator, Uuid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Naming conventions for database constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class with naming conventions."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _UUIDv7Generator:
    """Callable object for generating UUIDv7.

    Note: uuid.uuid7() was added in Python 3.13. For Python 3.12,
    we use uuid4() as a fallback. When Python 3.13+ is available,
    this will automatically use uuid7().
    """

    def __call__(self) -> uuid.UUID:
        """Generate a UUIDv7 (or v4 fallback) for database primary keys.

        UUIDv7 provides time-ordered IDs which are better for database indexing
        than random UUIDs (v4).
        """
        # uuid7 added in Python 3.13
        if hasattr(uuid, "uuid7"):
            return uuid.uuid7()  # type: ignore
        else:
            # Fallback to uuid4 for Python 3.12
            return uuid.uuid4()


class UUIDMixin:
    """Mixin for UUIDv7 primary key column."""

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:
        """Primary key as UUIDv7."""
        return mapped_column(
            Uuid,
            primary_key=True,
            insert_default=_UUIDv7Generator(),
            nullable=False,
        )


class _UTCNow:
    """Callable object for generating UTC timestamps."""

    def __call__(self) -> datetime:
        """Get current UTC datetime."""
        return datetime.now(UTC)


class TimestampMixin:
    """Mixin for created_at and updated_at timestamp columns."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        """Timestamp when record was created."""
        return mapped_column(
            DateTime(timezone=True),
            insert_default=_UTCNow(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        """Timestamp when record was last updated."""
        return mapped_column(
            DateTime(timezone=True),
            insert_default=_UTCNow(),
            onupdate=_UTCNow(),
            nullable=False,
        )


E = TypeVar("E", bound=Enum)


class EnumByValue(TypeDecorator[E]):
    """SQLAlchemy type for storing Enum by value instead of name.

    This ensures enums are stored as their string/int values in the database,
    making them more readable and resilient to enum name changes.
    """

    from sqlalchemy import String

    # impl must be set at class level for TypeDecorator - default to String
    impl: Any = String(50)
    cache_ok = True

    def __init__(self, enum_type: type[E], impl_type: Any | None = None) -> None:
        """Initialize with the enum type to use.

        Args:
            enum_type: The Enum class to use for conversion
            impl_type: Optional SQLAlchemy type to use (defaults to String(50))
        """
        self.enum_type = enum_type

        if impl_type is not None:
            self.impl = impl_type
        else:
            # Determine the appropriate SQL type based on enum value type
            first_member = next(iter(enum_type))
            if isinstance(first_member.value, str):
                from sqlalchemy import String

                self.impl = String(50)
            elif isinstance(first_member.value, int):
                from sqlalchemy import Integer

                self.impl = Integer()
            else:
                from sqlalchemy import String

                self.impl = String(50)

        super().__init__()

    def process_bind_param(self, value: E | None, _dialect: Any) -> Any:
        """Convert enum to value for database storage."""
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: Any, _dialect: Any) -> E | None:
        """Convert value from database to enum."""
        if value is None:
            return None
        return self.enum_type(value)


def get_async_session(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the database.

    Args:
        database_url: PostgreSQL connection string (must use asyncpg driver)

    Returns:
        Session factory that creates AsyncSession instances
    """
    # SQLite doesn't support pool_size/max_overflow
    if "sqlite" in database_url:
        engine = create_async_engine(
            database_url,
            echo=False,
        )
    else:
        # PostgreSQL with connection pooling
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
