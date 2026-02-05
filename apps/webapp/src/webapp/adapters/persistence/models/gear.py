"""Gear ORM models for persistence layer."""

import uuid
from datetime import datetime

from core.domain.value_objects.signal_chain_enums import GearType
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, EnumByValue, TimestampMixin, UUIDMixin
from .gear_model import GearModel
from .gear_source import GearSource

# Junction table for gear-tag many-to-many relationship
gear_tags_table = Table(
    "gear_tags",
    Base.metadata,
    Column("gear_id", Uuid, ForeignKey("gear.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class GearTag(UUIDMixin, Base):
    """Tag model for categorizing gear.

    Tags are shared across all gear items for consistent categorization.
    Examples: "metal", "high-gain", "blues", "clean", etc.

    Attributes:
        id: Primary key (UUIDv7)
        name: Tag name (unique, lowercase)
        gear_items: List of gear with this tag
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Relationship to gear (many-to-many)
    gear_items: Mapped[list["Gear"]] = relationship(
        "Gear",
        secondary=gear_tags_table,
        back_populates="tags",
    )


class GearMake(UUIDMixin, Base):
    """Manufacturer/make model for gear.

    Represents gear manufacturers (Fender, Marshall, etc.) for
    consistent manufacturer names across gear items.

    Attributes:
        id: Primary key (UUIDv7)
        name: Manufacturer name (unique)
        gear_items: List of gear from this manufacturer
    """

    __tablename__ = "gear_makes"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Relationship to gear
    gear_items: Mapped[list["Gear"]] = relationship(
        "Gear",
        back_populates="make",
    )


class Gear(UUIDMixin, TimestampMixin, Base):
    """Gear model representing amps, pedals, IRs, etc.

    Domain aggregate root for gear. Unified representation from any source.

    Attributes:
        id: Primary key (UUIDv7)
        name: Display name
        gear_type: Type of gear (amp, pedal, ir, etc.)
        description: Optional description
        manufacturer: Manufacturer name (legacy field, prefer make_id)
        make_id: Foreign key to gear_makes table
        thumbnail_url: Preview image URL
        is_public: Whether visible to all users
        source_id: Foreign key to gear_sources table (optional)
        created_at: When created in GTS
        updated_at: When last updated in GTS
        make: Manufacturer relationship
        source: Source tracking relationship
        models: List of downloadable model files
        tags: List of tags for categorization
    """

    __tablename__ = "gear"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gear_type: Mapped[GearType] = mapped_column(
        EnumByValue(GearType),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    make_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("gear_makes.id", ondelete="SET NULL"),
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("gear_sources.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    make: Mapped["GearMake | None"] = relationship(
        "GearMake",
        back_populates="gear_items",
    )
    source: Mapped["GearSource | None"] = relationship(
        "GearSource",
        back_populates="gear",
    )
    models: Mapped[list["GearModel"]] = relationship(
        "GearModel",
        back_populates="gear",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load models
    )
    tags: Mapped[list["GearTag"]] = relationship(
        "GearTag",
        secondary=gear_tags_table,
        back_populates="gear_items",
        lazy="selectin",  # Eager load tags
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_gear_type", "gear_type"),
        Index("ix_gear_is_public", "is_public"),
        Index("ix_gear_make_id", "make_id"),
        Index("ix_gear_source_id", "source_id"),
    )
