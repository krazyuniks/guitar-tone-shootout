"""BlockTypeRegistry service for managing built-in processor types."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import select

from core.domain.value_objects.block_category import BlockCategory
from webapp.adapters.persistence.models.block_type import BlockType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BlockTypeRegistry:
    """Registry for managing built-in processor types.

    Provides access to built-in audio processors (compressor, EQ, delay, etc.)
    that can be used in signal chains.
    """

    # Built-in processor definitions
    BUILTIN_PROCESSORS: ClassVar[list[dict]] = [
        {
            "name": "Compressor",
            "category": BlockCategory.DYNAMICS,
            "description": "Dynamic range compressor",
            "default_params": {
                "threshold": -20.0,
                "ratio": 4.0,
                "attack": 5.0,
                "release": 50.0,
                "makeup": 0.0,
            },
        },
        {
            "name": "EQ",
            "category": BlockCategory.EQ,
            "description": "Parametric equalizer",
            "default_params": {
                "low_freq": 100.0,
                "low_gain": 0.0,
                "mid_freq": 1000.0,
                "mid_gain": 0.0,
                "mid_q": 1.0,
                "high_freq": 8000.0,
                "high_gain": 0.0,
            },
        },
        {
            "name": "Delay",
            "category": BlockCategory.DELAY,
            "description": "Digital delay",
            "default_params": {
                "time": 500.0,
                "feedback": 30.0,
                "mix": 30.0,
            },
        },
        {
            "name": "Reverb",
            "category": BlockCategory.REVERB,
            "description": "Reverb effect",
            "default_params": {
                "size": 50.0,
                "decay": 3.0,
                "damping": 50.0,
                "mix": 30.0,
            },
        },
        {
            "name": "Noise Gate",
            "category": BlockCategory.UTILITY,
            "description": "Noise gate",
            "default_params": {
                "threshold": -60.0,
                "attack": 1.0,
                "release": 100.0,
            },
        },
    ]

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the registry with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_all_builtin_types(self) -> list[BlockType]:
        """Get all built-in block types.

        Initializes the database with built-in types on first call.

        Returns:
            List of all built-in block types
        """
        # Check if built-in types are already in the database
        stmt = select(BlockType)
        result = await self.session.execute(stmt)
        existing = result.scalars().all()

        # If no types exist, initialize them
        if not existing:
            await self._initialize_builtin_types()
            result = await self.session.execute(stmt)
            existing = result.scalars().all()

        return list(existing)

    async def get_by_category(self, category: BlockCategory) -> list[BlockType]:
        """Get block types filtered by category.

        Args:
            category: The block category to filter by

        Returns:
            List of block types in the specified category
        """
        # Ensure built-in types are initialized
        await self.get_all_builtin_types()

        stmt = select(BlockType).where(BlockType.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> BlockType | None:
        """Get a block type by name.

        Args:
            name: The name of the block type

        Returns:
            The block type if found, None otherwise
        """
        # Ensure built-in types are initialized
        await self.get_all_builtin_types()

        stmt = select(BlockType).where(BlockType.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _initialize_builtin_types(self) -> None:
        """Initialize the database with built-in block types (upsert by name)."""
        for processor in self.BUILTIN_PROCESSORS:
            stmt = select(BlockType).where(BlockType.name == processor["name"])
            result = await self.session.execute(stmt)
            if result.scalar_one_or_none() is None:
                block_type = BlockType(
                    name=processor["name"],
                    category=processor["category"],
                    description=processor.get("description"),
                    default_params=processor["default_params"],
                )
                self.session.add(block_type)

        await self.session.flush()
