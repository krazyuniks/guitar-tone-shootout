"""GearSource ORM model for tracking gear data sources."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .gear import Gear


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

    # Explicit annotations for inherited fields (for test compatibility)
    id: Mapped[uuid.UUID]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationship to gear (one-to-one)
    gear: Mapped["Gear"] = relationship(
        "Gear", back_populates="source", uselist=False, lazy="selectin"
    )

    # Composite index for source lookups
    __table_args__ = (
        Index("ix_gear_sources_source_lookup", "source_name", "source_record_id"),
    )
