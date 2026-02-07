"""PresetService for managing parameter presets."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from webapp.adapters.persistence.models.preset import Preset
from webapp.adapters.persistence.models.signal_chain import SignalChainBlock

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PresetService:
    """Service for managing parameter presets for signal chain blocks.

    Handles saving, loading, updating, deleting, and applying presets
    for built-in processors or gear settings.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def save_preset(
        self,
        *,
        signal_chain_block_id: UUID,
        name: str,
        params: dict[str, float],
    ) -> Preset:
        """Save a new preset for a signal chain block.

        Args:
            signal_chain_block_id: ID of the signal chain block
            name: Name for the preset
            params: Parameter values to save

        Returns:
            Created Preset instance

        Raises:
            ValueError: If name is empty or block doesn't exist
        """
        # Validate name
        if not name or not name.strip():
            raise ValueError("Preset name cannot be empty")

        # Validate block exists
        stmt = select(SignalChainBlock).where(SignalChainBlock.id == signal_chain_block_id)
        result = await self.session.execute(stmt)
        block = result.scalar_one_or_none()

        if not block:
            raise ValueError(f"Signal chain block {signal_chain_block_id} not found")

        # Create preset
        preset = Preset(
            signal_chain_block_id=signal_chain_block_id,
            name=name.strip(),
            params=params,
        )

        self.session.add(preset)
        await self.session.flush()
        await self.session.refresh(preset)

        return preset

    async def load_preset(self, preset_id: UUID) -> Preset | None:
        """Load a preset by ID.

        Args:
            preset_id: ID of the preset to load

        Returns:
            The preset if found, None otherwise
        """
        stmt = select(Preset).where(Preset.id == preset_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_presets_for_block(self, signal_chain_block_id: UUID) -> list[Preset]:
        """List all presets for a signal chain block.

        Args:
            signal_chain_block_id: ID of the signal chain block

        Returns:
            List of presets for the block
        """
        stmt = select(Preset).where(Preset.signal_chain_block_id == signal_chain_block_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_preset(self, preset_id: UUID) -> None:
        """Delete a preset.

        Args:
            preset_id: ID of the preset to delete
        """
        stmt = select(Preset).where(Preset.id == preset_id)
        result = await self.session.execute(stmt)
        preset = result.scalar_one_or_none()

        if preset:
            await self.session.delete(preset)
            await self.session.flush()

    async def update_preset(
        self,
        *,
        preset_id: UUID,
        name: str,
        params: dict[str, float],
    ) -> Preset | None:
        """Update an existing preset.

        Args:
            preset_id: ID of the preset to update
            name: New name for the preset
            params: New parameter values

        Returns:
            Updated preset if found, None otherwise
        """
        stmt = select(Preset).where(Preset.id == preset_id)
        result = await self.session.execute(stmt)
        preset = result.scalar_one_or_none()

        if not preset:
            return None

        preset.name = name
        preset.params = params
        await self.session.flush()
        await self.session.refresh(preset)

        return preset

    async def apply_preset_to_block(
        self,
        *,
        preset_id: UUID,
        signal_chain_block_id: UUID,
    ) -> None:
        """Apply a preset's parameters to a signal chain block.

        Args:
            preset_id: ID of the preset to apply
            signal_chain_block_id: ID of the block to update
        """
        # Load the preset
        preset = await self.load_preset(preset_id)
        if not preset:
            return

        # Load the block
        stmt = select(SignalChainBlock).where(SignalChainBlock.id == signal_chain_block_id)
        result = await self.session.execute(stmt)
        block = result.scalar_one_or_none()

        if not block:
            return

        # Apply the preset parameters to the block
        block.params = preset.params
        await self.session.flush()
