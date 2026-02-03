"""Gear ORM models for persistence layer."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform

from .base import Base, EnumByValue, TimestampMixin, UUIDMixin

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


class GearSource(UUIDMixin, TimestampMixin, Base):
    """Source tracking for gear data.

    Tracks where gear came from (T3K, user upload, etc.) for sync
    and attribution purposes.

    Attributes:
        id: Primary key (UUIDv7)
        source_name: Name of source (e.g., 't3k', 'user_upload')
        source_record_id: ID in the source system
        source_updated_at: Last update time in source system
        created_at: When source record was created
        updated_at: When source record was last updated
        gear: The gear item this source belongs to
    """

    __tablename__ = "gear_sources"

    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationship to gear (one-to-one)
    gear: Mapped["Gear"] = relationship("Gear", back_populates="source", uselist=False)

    # Composite index for source lookups
    __table_args__ = (
        Index("ix_gear_sources_source_lookup", "source_name", "source_record_id"),
    )


class GearModel(UUIDMixin, Base):
    """Downloadable model file for gear.

    Represents a specific model file variant (platform, size) for a
    piece of gear. A single gear item can have multiple model files.

    Attributes:
        id: Primary key (UUIDv7)
        gear_id: Foreign key to gear table
        platform: Target platform (NAM, AIDA-X, etc.)
        size: Model size variant (standard, lite, etc.)
        file_path: Local path to model file (if downloaded)
        download_url: URL to download the model
        download_status: Current download status
        file_hash: SHA256 hash for integrity verification
        gear: The gear item this model belongs to
    """

    __tablename__ = "gear_models"

    gear_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("gear.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[Platform] = mapped_column(
        EnumByValue(Platform),
        nullable=False,
    )
    size: Mapped[ModelSize] = mapped_column(
        EnumByValue(ModelSize),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_status: Mapped[DownloadStatus] = mapped_column(
        EnumByValue(DownloadStatus),
        nullable=False,
        default=DownloadStatus.PENDING,
    )
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationship to gear
    gear: Mapped["Gear"] = relationship("Gear", back_populates="models")

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_gearmodel_gear_id", "gear_id"),
        Index("ix_gearmodel_platform", "platform"),
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
