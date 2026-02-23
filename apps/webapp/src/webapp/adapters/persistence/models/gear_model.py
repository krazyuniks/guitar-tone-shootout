"""GearModel ORM model for persistence layer."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.signal_chain_enums import ModelSize, Platform

from .base import Base, EnumByValue, UUIDMixin, UuidType

if TYPE_CHECKING:
    from .gear import Gear
    from .user_gear import UserGear


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

    # Explicit annotation for inherited id field (for test compatibility)
    id: Mapped[uuid.UUID]

    gear_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
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
    gear: Mapped[Gear] = relationship("Gear", back_populates="models", lazy="raise")  # type: ignore

    # Relationship to user_gear (users who have this model in their library)
    user_gear: Mapped[list[UserGear]] = relationship(
        "UserGear",
        back_populates="gear_model",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_gearmodel_gear_id", "gear_id"),
        Index("ix_gearmodel_platform", "platform"),
    )
