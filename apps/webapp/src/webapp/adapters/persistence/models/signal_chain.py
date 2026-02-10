"""SignalChain ORM models for persistence layer."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.domain.value_objects.signal_chain_enums import (
    GearType,
    Platform,
)

from .base import Base, EnumByValue, TimestampMixin, UUIDMixin, UuidType
from .block_type import BlockType
from .preset import Preset

if TYPE_CHECKING:
    from .user import User


class SignalChain(UUIDMixin, TimestampMixin, Base):
    """SignalChain model for user-created signal chains.

    Represents a composition of gear that can be processed together.
    Follows signal chain grammar rules for valid compositions.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        name: Display name for the signal chain
        description: Optional description
        platform: Target platform (NAM, AIDA-X, etc.)
        created_at: When the chain was created
        updated_at: When the chain was last updated
        user: Reference to the User
        blocks: List of blocks in this chain
    """

    __tablename__ = "signal_chains"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[Platform] = mapped_column(
        EnumByValue(Platform),
        nullable=False,
        default=Platform.NAM,
        server_default="nam",
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("signal_chain_groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="signal_chains",
        lazy="raise",
    )
    blocks: Mapped[list[SignalChainBlock]] = relationship(
        "SignalChainBlock",
        back_populates="signal_chain",
        cascade="all, delete-orphan",
        order_by="SignalChainBlock.position",
        lazy="raise",
    )
    group: Mapped[SignalChainGroup | None] = relationship(
        "SignalChainGroup",
        foreign_keys=[group_id],
        lazy="raise",
    )

    # Indexes
    __table_args__ = (
        Index("ix_signal_chains_user_id", "user_id"),
        Index("ix_signal_chains_group_id", "group_id"),
    )


class SignalChainBlock(UUIDMixin, Base):
    """Individual block in a signal chain.

    Represents one component (pedal, amp, full-rig, IR, or post-effect)
    in the signal chain. Blocks are ordered by position.

    Can reference either:
    - UserGear (user's library item) via user_gear_id + gear_type
    - BlockType (built-in processor) via block_type_id

    Attributes:
        id: Primary key (UUIDv7)
        signal_chain_id: Foreign key to signal_chains table
        position: Order in the chain (0-indexed)
        user_gear_id: Reference to UserGear item (nullable when using BlockType)
        gear_type: Type of gear (nullable when using BlockType)
        block_type_id: Foreign key to block_types table (nullable when using UserGear)
        params: Parameter values as JSON (default empty dict)
        signal_chain: Reference to the SignalChain
        block_type: Reference to the BlockType
        presets: List of parameter presets for this block
    """

    __tablename__ = "signal_chain_blocks"

    signal_chain_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("signal_chains.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    user_gear_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        nullable=True,
    )
    gear_type: Mapped[GearType | None] = mapped_column(
        EnumByValue(GearType),
        nullable=True,
    )
    block_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("block_types.id", ondelete="CASCADE"),
        nullable=True,
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    signal_chain: Mapped[SignalChain] = relationship(
        "SignalChain",
        back_populates="blocks",
        lazy="raise",
    )
    block_type: Mapped[BlockType | None] = relationship(
        "BlockType",
        back_populates="blocks",
        lazy="raise",
    )
    presets: Mapped[list[Preset]] = relationship(
        "Preset",
        back_populates="signal_chain_block",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_signal_chain_blocks_chain_id", "signal_chain_id"),
        Index("ix_signal_chain_blocks_position", "signal_chain_id", "position"),
    )


class SignalChainGroup(UUIDMixin, TimestampMixin, Base):
    """SignalChainGroup model for permutation-based comparisons.

    Groups allow users to compare multiple gear options at specific
    positions in a chain. The system generates permutations to test
    all combinations.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        name: Display name for the group
        description: Optional description
        base_chain_id: Foreign key to signal_chains table (base chain)
        slot_positions: List of positions that can vary (stored as JSON)
        gear_options: Gear options per slot (stored as JSON)
        include_null: Whether to include "no gear" as an option
        created_at: When created
        updated_at: When last updated
        user: Reference to the User
        base_chain: Reference to the base SignalChain
    """

    __tablename__ = "signal_chain_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_chain_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType(),
        ForeignKey("signal_chains.id", ondelete="CASCADE"),
        nullable=True,
    )
    slot_positions: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    gear_options: Mapped[dict[int, list[str]]] = mapped_column(JSON, nullable=False, default=dict)
    include_null: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="signal_chain_groups",
        lazy="raise",
    )
    base_chain: Mapped[SignalChain | None] = relationship(
        "SignalChain",
        foreign_keys=[base_chain_id],
        lazy="raise",
    )

    # Indexes
    __table_args__ = (
        Index("ix_signal_chain_groups_user_id", "user_id"),
    )
