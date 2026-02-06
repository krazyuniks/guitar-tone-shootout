"""Unit tests for BlockTypeRegistry.

Tests the registry for managing built-in processor types.
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
from webapp.adapters.persistence.models.block_type import BlockType


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session with transaction rollback."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestBlockTypeRegistry:
    """Tests for BlockTypeRegistry built-in processor management."""

    async def test_registry_exists(self) -> None:
        """Verify BlockTypeRegistry can be imported."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        assert BlockTypeRegistry is not None

    async def test_registry_loads_builtin_compressor(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry provides built-in compressor block type."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)

        # Registry should provide access to built-in processor templates
        block_types = await registry.get_all_builtin_types()

        assert block_types is not None
        assert len(block_types) > 0

        # Should include at least a compressor
        compressor = next(
            (bt for bt in block_types if "compressor" in bt.name.lower()),
            None,
        )
        assert compressor is not None
        assert compressor.category == BlockCategory.DYNAMICS

    async def test_registry_loads_builtin_eq(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry provides built-in EQ block type."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)
        block_types = await registry.get_all_builtin_types()

        # Should include an EQ
        eq = next(
            (bt for bt in block_types if bt.category == BlockCategory.EQ),
            None,
        )
        assert eq is not None
        assert eq.default_params is not None

    async def test_registry_loads_builtin_delay(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry provides built-in delay block type."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)
        block_types = await registry.get_all_builtin_types()

        # Should include delay
        delay = next(
            (bt for bt in block_types if bt.category == BlockCategory.DELAY),
            None,
        )
        assert delay is not None

    async def test_registry_loads_builtin_reverb(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry provides built-in reverb block type."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)
        block_types = await registry.get_all_builtin_types()

        # Should include reverb
        reverb = next(
            (bt for bt in block_types if bt.category == BlockCategory.REVERB),
            None,
        )
        assert reverb is not None

    async def test_registry_loads_builtin_noise_gate(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry provides built-in noise gate block type."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)
        block_types = await registry.get_all_builtin_types()

        # Should include noise gate (utility category)
        noise_gate = next(
            (bt for bt in block_types if "gate" in bt.name.lower()),
            None,
        )
        assert noise_gate is not None
        assert noise_gate.category == BlockCategory.UTILITY

    async def test_registry_get_by_category(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry can filter block types by category."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)

        # Should be able to get only EQ blocks
        eq_blocks = await registry.get_by_category(BlockCategory.EQ)

        assert eq_blocks is not None
        assert len(eq_blocks) > 0
        assert all(bt.category == BlockCategory.EQ for bt in eq_blocks)

    async def test_registry_get_by_name(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry can retrieve block type by name."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)

        # Should be able to get a specific block type by name
        compressor = await registry.get_by_name("Compressor")

        assert compressor is not None
        assert compressor.name == "Compressor"
        assert compressor.category == BlockCategory.DYNAMICS

    async def test_registry_initializes_database(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry initializes built-in types in database on first call."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)

        # First call should initialize the database
        block_types = await registry.get_all_builtin_types()
        assert len(block_types) > 0

        # Verify they're actually persisted in the database
        from sqlalchemy import select

        result = await session.execute(select(BlockType))
        persisted = result.scalars().all()

        assert len(persisted) == len(block_types)

    async def test_registry_returns_same_instances_on_multiple_calls(
        self,
        session: AsyncSession,
    ) -> None:
        """Test registry returns consistent data on multiple calls."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)

        # Get built-in types twice
        first_call = await registry.get_all_builtin_types()
        second_call = await registry.get_all_builtin_types()

        # Should return the same count
        assert len(first_call) == len(second_call)

        # Should have the same names
        first_names = {bt.name for bt in first_call}
        second_names = {bt.name for bt in second_call}
        assert first_names == second_names

    async def test_registry_builtin_types_have_default_params(
        self,
        session: AsyncSession,
    ) -> None:
        """Test all built-in types have default parameters defined."""
        from webapp.services.block_type_registry import BlockTypeRegistry

        registry = BlockTypeRegistry(session)
        block_types = await registry.get_all_builtin_types()

        # All built-in types should have default_params
        for bt in block_types:
            assert bt.default_params is not None
            assert isinstance(bt.default_params, dict)
