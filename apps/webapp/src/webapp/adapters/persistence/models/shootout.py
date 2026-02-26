"""Shootout and DITrack ORM models for persistence layer."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from .base import (
    AudioChecksumType,
    Base,
    EnumByValue,
    TimestampMixin,
    UUIDMixin,
    UuidType,
    WaveformDataType,
)

if TYPE_CHECKING:
    from .shootout_comment import ShootoutComment
    from .signal_chain import SignalChain
    from .user import User


class ShootoutStatus(str, Enum):
    """Status enum for shootout processing."""

    DRAFT = "draft"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DITrack(UUIDMixin, TimestampMixin, Base):
    """DITrack model for user-uploaded DI recordings.

    Represents a clean guitar recording that can be processed
    through various signal chains for comparison.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        name: Display name for the track
        file_path: Path to the audio file
        original_filename: Original uploaded filename
        duration_seconds: Track duration in seconds
        sample_rate: Audio sample rate in Hz
        channels: Number of audio channels (1=mono, 2=stereo)
        waveform: Waveform visualization data
        description: Optional description
        guitar: Guitar used for recording (optional)
        pickup: Pickup position/type (optional)
        tuning: Tuning used for recording (optional)
        checksum: Audio file checksum for integrity (optional)
        created_at: When uploaded
        updated_at: When last updated
        user: Reference to the User
        shootouts: Shootouts using this DI track
    """

    __tablename__ = "core_di_tracks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("core_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=44100)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waveform: Mapped[Any] = mapped_column(WaveformDataType(), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    guitar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tuning: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checksum: Mapped[Any] = mapped_column(AudioChecksumType(), nullable=True)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="di_tracks",
        lazy="raise",
    )
    shootouts: Mapped[list[Shootout]] = relationship(
        "Shootout",
        back_populates="di_track",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Indexes
    __table_args__ = (Index("ix_di_tracks_user_id", "user_id"),)


class Shootout(UUIDMixin, TimestampMixin, Base):
    """Shootout model for tone comparison sessions.

    Represents a comparison of multiple signal chains using a common
    DI track. Manages the collection of chains and processing state.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        di_track_id: Foreign key to di_tracks table (nullable)
        name: Display name for the shootout
        description: Optional description
        status: Processing status (pending, processing, completed, failed)
        video_path: Path to output video (after processing)
        video_status: Video rendering status (nullable)
        video_job_id: Job ID for video rendering (nullable)
        output_path: Path to master audio file (after processing)
        created_at: When created
        updated_at: When last updated
        user: Reference to the User
        di_track: Reference to the DITrack
        chains: List of chain links in this shootout
    """

    __tablename__ = "core_shootouts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("core_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    di_track_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("core_di_tracks.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = synonym("name")  # Alias for backwards compatibility
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ShootoutStatus] = mapped_column(
        EnumByValue(ShootoutStatus),
        nullable=False,
        default=ShootoutStatus.DRAFT,
    )
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    video_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="shootouts",
        lazy="raise",
    )
    di_track: Mapped[DITrack | None] = relationship(
        "DITrack",
        back_populates="shootouts",
        lazy="raise",
    )
    chains: Mapped[list[ShootoutChain]] = relationship(
        "ShootoutChain",
        back_populates="shootout",
        cascade="all, delete-orphan",
        order_by="ShootoutChain.position",
        lazy="raise",
    )
    comments: Mapped[list[ShootoutComment]] = relationship(
        "ShootoutComment",
        back_populates="shootout",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Indexes
    __table_args__ = (
        Index("ix_shootouts_user_id", "user_id"),
        Index("ix_shootouts_status", "status"),
    )


class ShootoutChain(UUIDMixin, Base):
    """Junction model linking shootouts to signal chains.

    Represents a signal chain included in a shootout, with positioning
    and labelling for display.

    Attributes:
        id: Primary key (UUIDv7)
        shootout_id: Foreign key to shootouts table
        signal_chain_id: Foreign key to signal_chains table
        position: Order in the shootout (0-indexed)
        label: Display label for this chain in the shootout
        shootout: Reference to the Shootout
        signal_chain: Reference to the SignalChain
        segments: Processed audio segments for this chain
    """

    __tablename__ = "core_shootout_chains"

    shootout_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("core_shootouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_chain_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("core_signal_chains.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    shootout: Mapped[Shootout] = relationship(
        "Shootout",
        back_populates="chains",
        lazy="raise",
    )
    signal_chain: Mapped[SignalChain] = relationship(
        "SignalChain",
        lazy="raise",
    )
    segments: Mapped[list[AudioSegment]] = relationship(
        "AudioSegment",
        back_populates="shootout_chain",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Indexes
    __table_args__ = (
        Index("ix_shootout_chains_shootout_id", "shootout_id"),
        Index("ix_shootout_chains_position", "shootout_id", "position"),
    )


class AudioSegment(UUIDMixin, Base):
    """AudioSegment model for processed audio segments.

    Represents a processed audio segment from a shootout chain,
    with loudness measurement data.

    Attributes:
        id: Primary key (UUIDv7)
        shootout_chain_id: Foreign key to shootout_chains table
        file_path: Path to the processed audio file
        duration_seconds: Segment duration in seconds
        integrated_lufs: Integrated loudness (LUFS)
        peak_dbfs: Peak level (dBFS)
        shootout_chain: Reference to the ShootoutChain
    """

    __tablename__ = "core_audio_segments"

    shootout_chain_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("core_shootout_chains.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    integrated_lufs: Mapped[float] = mapped_column(Float, nullable=False)
    peak_dbfs: Mapped[float] = mapped_column(Float, nullable=False)
    waveform: Mapped[Any] = mapped_column(WaveformDataType(), nullable=True)

    # Relationship
    shootout_chain: Mapped[ShootoutChain] = relationship(
        "ShootoutChain",
        back_populates="segments",
        lazy="raise",
    )

    # Index
    __table_args__ = (Index("ix_audio_segments_chain_id", "shootout_chain_id"),)
