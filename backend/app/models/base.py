"""Base model class and mixins for SQLAlchemy models.

Provides consistent naming conventions and common functionality across all models.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming conventions for database constraints
# This ensures consistent, predictable constraint names across all tables
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Includes metadata with naming conventions for consistent constraint naming.
    """

    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class UUIDMixin:
    """Mixin that adds a UUID primary key to models."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
