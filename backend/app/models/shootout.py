"""Shootout and ToneSelection models for storing comparison configurations.

Replaces INI file configuration with database-backed storage.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Shootout(Base, UUIDMixin, TimestampMixin):
    """Shootout configuration for comparing multiple tones.

    Stores all settings for a tone comparison including DI track info,
    output settings, and processing state. Related tone selections are
    stored in the ToneSelection table.
    """

    __tablename__ = "shootouts"
    __table_args__ = (Index("ix_shootouts_user_created", "user_id", "created_at"),)

    # Owner of the shootout
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Shootout metadata
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    # DI track reference
    di_track_path: Mapped[str] = mapped_column(String(1000))
    di_track_original_name: Mapped[str] = mapped_column(String(255))

    # Output settings
    output_format: Mapped[str] = mapped_column(String(10), default="mp4")
    sample_rate: Mapped[int] = mapped_column(default=44100)

    # Optional metadata (guitar/pickup info)
    guitar: Mapped[str | None] = mapped_column(String(255))
    pickup: Mapped[str | None] = mapped_column(String(255))

    # Processing state
    is_processed: Mapped[bool] = mapped_column(default=False)
    output_path: Mapped[str | None] = mapped_column(String(1000))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="shootouts")
    tone_selections: Mapped[list["ToneSelection"]] = relationship(
        back_populates="shootout",
        cascade="all, delete-orphan",
        order_by="ToneSelection.position",
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="shootout")

    def __repr__(self) -> str:
        """Return string representation of the shootout."""
        return f"<Shootout {self.id} name='{self.name}'>"


class ToneSelection(Base, UUIDMixin, TimestampMixin):
    """Selected tone/model for a shootout comparison.

    Stores references to Tone 3000 tones and models along with cached
    metadata for display when offline.
    """

    __tablename__ = "tone_selections"
    __table_args__ = (
        Index("ix_tone_selections_shootout_position", "shootout_id", "position"),
    )

    # Parent shootout
    shootout_id: Mapped[UUID] = mapped_column(
        ForeignKey("shootouts.id", ondelete="CASCADE"),
        index=True,
    )

    # Tone 3000 references
    tone3000_tone_id: Mapped[int] = mapped_column(index=True)
    tone3000_model_id: Mapped[int] = mapped_column(index=True)

    # Cached metadata from Tone 3000 (for display when offline)
    tone_title: Mapped[str] = mapped_column(String(255))
    model_name: Mapped[str] = mapped_column(String(255))
    model_size: Mapped[str] = mapped_column(String(20))  # standard, lite, feather, nano
    gear_type: Mapped[str] = mapped_column(String(20))  # amp, pedal, full-rig

    # Display name override (optional)
    display_name: Mapped[str | None] = mapped_column(String(255))

    # Optional IR override (path to IR file)
    ir_path: Mapped[str | None] = mapped_column(String(1000))

    # Processing options
    highpass: Mapped[bool] = mapped_column(default=True)

    # Effects chain (stored as JSON string for simplicity)
    effects_json: Mapped[str | None] = mapped_column(Text)

    # Ordering in comparison
    position: Mapped[int] = mapped_column(default=0)

    # Relationship
    shootout: Mapped["Shootout"] = relationship(back_populates="tone_selections")

    def __repr__(self) -> str:
        """Return string representation of the tone selection."""
        return f"<ToneSelection {self.id} tone='{self.tone_title}' pos={self.position}>"
