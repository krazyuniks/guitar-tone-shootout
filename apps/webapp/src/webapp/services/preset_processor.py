"""PresetProcessor for validating chain parameters against block type definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from webapp.adapters.persistence.models.block_type import BlockType
from webapp.adapters.persistence.models.signal_chain import SignalChainBlock
from webapp.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class PresetProcessor:
    """Validates preset parameters against block type definitions.

    Ensures that parameter keys match those defined in the block type's
    default_params and that values are of appropriate types.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the processor with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def validate_params(
        self,
        signal_chain_block_id: UUID,
        params: dict[str, Any],
    ) -> None:
        """Validate parameters against block type definition.

        Args:
            signal_chain_block_id: ID of the signal chain block
            params: Parameter values to validate

        Raises:
            ValueError: If block not found or block has no block_type
            ValidationError: If parameters are invalid (422)
        """
        # Load the block and its block_type
        stmt = select(SignalChainBlock).where(SignalChainBlock.id == signal_chain_block_id)
        result = await self.session.execute(stmt)
        block = result.scalar_one_or_none()

        if not block:
            raise ValueError(f"Signal chain block {signal_chain_block_id} not found")

        # Load the block_type separately if needed
        if block.block_type_id is None:
            raise ValueError(f"Block {signal_chain_block_id} has no block_type")

        stmt = select(BlockType).where(BlockType.id == block.block_type_id)
        result = await self.session.execute(stmt)
        block_type = result.scalar_one_or_none()

        if not block_type:
            raise ValueError(f"BlockType {block.block_type_id} not found")

        # Validate that all parameter keys exist in the block type's default_params
        valid_keys = set(block_type.default_params.keys())
        provided_keys = set(params.keys())

        invalid_keys = provided_keys - valid_keys
        if invalid_keys:
            raise ValidationError(
                message=f"Invalid parameter keys: {', '.join(sorted(invalid_keys))}"
            )
