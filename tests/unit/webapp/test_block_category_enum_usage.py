"""Unit tests verifying BlockType.category uses BlockCategory enum.

The acceptance criteria states BlockType should have a category field,
and BlockCategory enum should include the values from wiki:334-342.

This test verifies that BlockType.category is typed as BlockCategory enum,
not just a plain string.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.domain.value_objects.block_category import BlockCategory
from webapp.adapters.persistence.models.base import Base


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestBlockCategoryEnumUsage:
    """Tests verifying BlockType.category uses BlockCategory enum type."""

    async def test_block_type_category_accepts_enum_value(self, session: AsyncSession) -> None:
        """BlockType.category should accept BlockCategory enum values."""
        from webapp.adapters.persistence.models.block_type import BlockType

        # Create with each BlockCategory enum value
        for category in BlockCategory:
            block_type = BlockType(
                name=f"Test {category.value}",
                category=category,  # Should accept enum directly
                default_params={},
            )
            session.add(block_type)
            await session.flush()

            # Verify it's stored as the enum type
            assert block_type.category == category
            assert isinstance(block_type.category, BlockCategory)

    async def test_block_type_category_rejects_invalid_string(self, session: AsyncSession) -> None:
        """BlockType.category should reject invalid category strings."""
        from webapp.adapters.persistence.models.block_type import BlockType

        # Try to create with invalid category
        block_type = BlockType(
            name="Invalid Block",
            category="invalid_category",  # Not a valid BlockCategory value
            default_params={},
        )
        session.add(block_type)

        # Should raise exception on commit due to enum constraint
        with pytest.raises(Exception):  # Could be IntegrityError or ValueError
            await session.commit()

    async def test_block_type_category_persists_as_enum(self, session: AsyncSession) -> None:
        """BlockType.category should persist and retrieve as BlockCategory enum."""
        from sqlalchemy import select

        from webapp.adapters.persistence.models.block_type import BlockType

        # Create with REVERB category
        block_type = BlockType(
            name="Hall Reverb",
            category=BlockCategory.REVERB,
            default_params={"size": 1.0},
        )
        session.add(block_type)
        await session.commit()

        # Query back
        result = await session.execute(select(BlockType).where(BlockType.name == "Hall Reverb"))
        saved = result.scalar_one()

        # Verify it's still an enum (not converted to string)
        assert saved.category == BlockCategory.REVERB
        assert isinstance(saved.category, BlockCategory)
        assert saved.category.value == "reverb"

    async def test_block_type_category_supports_all_enum_values(
        self, session: AsyncSession
    ) -> None:
        """BlockType.category should support all BlockCategory enum values from wiki:334-342."""
        from sqlalchemy import select

        from webapp.adapters.persistence.models.block_type import BlockType

        # Create blocks for each category mentioned in acceptance criteria
        expected_categories = [
            BlockCategory.UTILITY,
            BlockCategory.EQ,
            BlockCategory.DYNAMICS,
            BlockCategory.MODULATION,
            BlockCategory.DELAY,
            BlockCategory.REVERB,
        ]

        for idx, category in enumerate(expected_categories):
            block_type = BlockType(
                name=f"Test Block {idx}",
                category=category,
                default_params={},
            )
            session.add(block_type)

        await session.commit()

        # Verify all were saved
        result = await session.execute(select(BlockType))
        saved_blocks = result.scalars().all()

        assert len(saved_blocks) == len(expected_categories)
        saved_categories = {block.category for block in saved_blocks}
        assert saved_categories == set(expected_categories)
