"""BlockType ORM model for built-in processors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gts.domain.value_objects.block_category import BlockCategory

from .base import Base, EnumByValue, UUIDMixin

if TYPE_CHECKING:
    from .signal_chain import SignalChainBlock


class BlockType(UUIDMixin, Base):
    """Built-in processor type definitions.

    Represents built-in audio processors (compressor, EQ, etc.) that
    can be used in signal chains beyond captured gear.

    Attributes:
        id: Primary key (UUIDv7)
        name: Processor name (e.g., 'Compressor', 'EQ')
        category: Category from BlockCategory enum
        description: Optional description
        default_params: Default parameter values as JSON
        blocks: Blocks using this block type
    """

    __tablename__ = "block_types"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[BlockCategory] = mapped_column(
        EnumByValue(BlockCategory),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    blocks: Mapped[list[SignalChainBlock]] = relationship(
        "SignalChainBlock",
        back_populates="block_type",
        lazy="raise",
    )
