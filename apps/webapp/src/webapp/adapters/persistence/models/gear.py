"""Gear ORM models for persistence layer."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gear_model import GearModel
    from .gear_source import GearSource

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.domain.value_objects.signal_chain_enums import GearType

from .base import Base, EnumByValue, TimestampMixin, UUIDMixin, UuidType


def _slugify(text: str, manufacturer: str | None = None) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: The text to slugify
        manufacturer: Optional manufacturer name to prepend

    Returns:
        A lowercase, hyphenated slug
    """
    # Check if manufacturer is already in the name
    if manufacturer:
        # Case-insensitive check if name starts with manufacturer
        if text.lower().startswith(manufacturer.lower()):
            # Manufacturer already in name, don't duplicate
            combined = text
        else:
            # Prepend manufacturer
            combined = f"{manufacturer} {text}"
    else:
        combined = text

    # Convert to lowercase
    slug = combined.lower()
    # Normalize unicode characters (ö -> o, etc.)
    import unicodedata
    slug = unicodedata.normalize('NFKD', slug)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9-]+', '-', slug)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug

# Junction table for gear-tag many-to-many relationship
gear_tags_table = Table(
    "gear_tags",
    Base.metadata,
    Column("gear_id", UuidType(), ForeignKey("gear.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UuidType(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
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
    gear_items: Mapped[list[Gear]] = relationship(
        "Gear",
        secondary=gear_tags_table,
        back_populates="tags",
        lazy="raise",
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
    gear_items: Mapped[list[Gear]] = relationship(
        "Gear",
        back_populates="make",
        lazy="raise",
    )


class Gear(UUIDMixin, TimestampMixin, Base):
    """Gear model representing amps, pedals, IRs, etc.

    Domain aggregate root for gear. Unified representation from any source.

    Attributes:
        id: Primary key (UUIDv7)
        name: Display name
        gear_type: Type of gear (amp, pedal, ir, etc.)
        platform: Primary platform for this gear (optional, derived from models)
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
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gear_type: Mapped[GearType] = mapped_column(
        EnumByValue(GearType),
        nullable=False,
    )
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    make_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("gear_makes.id", ondelete="SET NULL"),
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("gear_sources.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    make: Mapped[GearMake | None] = relationship(
        "GearMake",
        back_populates="gear_items",
        lazy="raise",
    )
    source: Mapped[GearSource | None] = relationship(
        "GearSource",
        back_populates="gear",
        lazy="raise",
    )
    models: Mapped[list[GearModel]] = relationship(
        "GearModel",
        back_populates="gear",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    tags: Mapped[list[GearTag]] = relationship(
        "GearTag",
        secondary=gear_tags_table,
        back_populates="gear_items",
        lazy="raise",
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_gear_type", "gear_type"),
        Index("ix_gear_is_public", "is_public"),
        Index("ix_gear_make_id", "make_id"),
        Index("ix_gear_source_id", "source_id"),
    )


# Event listener to auto-generate slug before insert
@event.listens_for(Gear, 'before_insert')
def generate_slug(mapper, connection, target):
    """Automatically generate slug if not provided."""
    if not target.slug:
        target.slug = _slugify(target.name, target.manufacturer)
