"""Preset ORM model for signal chain block parameter values."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin

if TYPE_CHECKING:
    from .signal_chain import SignalChainBlock


class Preset(UUIDMixin, Base):
    """Parameter preset for a signal chain block.

    Stores parameter values for built-in processors or gear settings.

    Attributes:
        id: Primary key (UUIDv7)
        signal_chain_block_id: Foreign key to signal_chain_blocks table
        name: Preset name
        params: Parameter values as JSON
        signal_chain_block: Reference to the SignalChainBlock
    """

    __tablename__ = "presets"

    signal_chain_block_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("signal_chain_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationship
    signal_chain_block: Mapped[SignalChainBlock] = relationship(
        "SignalChainBlock",
        back_populates="presets",
    )

    # Index
    __table_args__ = (
        Index("ix_presets_block_id", "signal_chain_block_id"),
    )
