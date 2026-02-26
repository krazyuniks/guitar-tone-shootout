"""Unit tests verifying BlockType and Preset models exist in separate files.

The task spec requires these models to be in dedicated files:
- apps/webapp/src/webapp/adapters/persistence/models/block_type.py
- apps/webapp/src/webapp/adapters/persistence/models/preset.py

Currently they're defined in signal_chain.py. These tests verify
the expected module structure.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


class TestBlockTypeModelLocation:
    """Tests verifying BlockType model exists in dedicated file."""

    async def test_block_type_importable_from_dedicated_module(self) -> None:
        """BlockType should be importable from block_type.py module."""
        # This will fail if block_type.py doesn't exist or doesn't export BlockType
        from webapp.adapters.persistence.models.block_type import BlockType

        assert BlockType is not None
        assert BlockType.__tablename__ == "core_block_types"

    async def test_block_type_has_required_fields(self) -> None:
        """BlockType model should have name, category, default_params fields."""
        from webapp.adapters.persistence.models.block_type import BlockType

        # Verify field attributes exist
        assert hasattr(BlockType, "name")
        assert hasattr(BlockType, "category")
        assert hasattr(BlockType, "default_params")

    async def test_block_type_category_uses_block_category_enum(self) -> None:
        """BlockType.category should use BlockCategory enum for validation."""
        from gts.domain.value_objects.block_category import BlockCategory
        from webapp.adapters.persistence.models.block_type import BlockType

        # Create instance with valid category
        block_type = BlockType(
            name=f"Test EQ_{uuid.uuid4().hex[:8]}",
            category=BlockCategory.EQ,
            default_params={},
        )
        assert block_type.category == BlockCategory.EQ

    async def test_block_type_persists_to_database(self, session: AsyncSession) -> None:
        """BlockType should be persistable to database."""
        from sqlalchemy import select

        from gts.domain.value_objects.block_category import BlockCategory
        from webapp.adapters.persistence.models.block_type import BlockType

        suffix = uuid.uuid4().hex[:8]
        # Create and persist
        block_type = BlockType(
            name=f"Compressor_{suffix}",
            category=BlockCategory.DYNAMICS,
            default_params={"ratio": 4.0, "threshold": -10.0},
        )
        session.add(block_type)
        await session.commit()

        # Query back
        result = await session.execute(
            select(BlockType).where(BlockType.name == f"Compressor_{suffix}")
        )
        saved = result.scalar_one()

        assert saved.name == f"Compressor_{suffix}"
        assert saved.category == BlockCategory.DYNAMICS
        assert saved.default_params == {"ratio": 4.0, "threshold": -10.0}

    async def test_block_type_name_is_unique(self, session: AsyncSession) -> None:
        """BlockType.name should have unique constraint."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        from gts.domain.value_objects.block_category import BlockCategory
        from webapp.adapters.persistence.models.block_type import BlockType

        shared_name = f"Reverb_{uuid.uuid4().hex[:8]}"
        # Create first block type
        block_type1 = BlockType(
            name=shared_name,
            category=BlockCategory.REVERB,
            default_params={},
        )
        session.add(block_type1)
        await session.commit()

        # Try to create duplicate
        block_type2 = BlockType(
            name=shared_name,  # Same name
            category=BlockCategory.DELAY,
            default_params={},
        )
        session.add(block_type2)

        with pytest.raises(IntegrityError):
            await session.commit()


class TestPresetModelLocation:
    """Tests verifying Preset model exists in dedicated file."""

    async def test_preset_importable_from_dedicated_module(self) -> None:
        """Preset should be importable from preset.py module."""
        # This will fail if preset.py doesn't exist or doesn't export Preset
        from webapp.adapters.persistence.models.preset import Preset

        assert Preset is not None
        assert Preset.__tablename__ == "core_presets"

    async def test_preset_has_required_fields(self) -> None:
        """Preset model should have signal_chain_block_id, name, params fields."""
        from webapp.adapters.persistence.models.preset import Preset

        # Verify field attributes exist
        assert hasattr(Preset, "signal_chain_block_id")
        assert hasattr(Preset, "name")
        assert hasattr(Preset, "params")

    async def test_preset_persists_to_database(self, session: AsyncSession) -> None:
        """Preset should be persistable to database with parameter values."""

        from sqlalchemy import select

        from gts.domain.value_objects.block_category import BlockCategory
        from gts.domain.value_objects.signal_chain_enums import Platform
        from webapp.adapters.persistence.models.block_type import BlockType
        from webapp.adapters.persistence.models.preset import Preset
        from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
        from webapp.adapters.persistence.models.user import User

        suffix = uuid.uuid4().hex[:8]
        # Create user and chain
        user = User(
            username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
        )
        session.add(user)
        await session.commit()

        chain = SignalChain(
            user_id=user.id,
            name="Test Chain",
            platform=Platform.NAM,
        )
        session.add(chain)
        await session.commit()

        # Create block type and block
        block_type = BlockType(
            name=f"EQ_{suffix}",
            category=BlockCategory.EQ,
            default_params={},
        )
        session.add(block_type)
        await session.commit()

        block = SignalChainBlock(
            signal_chain_id=chain.id,
            position=0,
            block_type_id=block_type.id,
        )
        session.add(block)
        await session.commit()

        # Create preset
        preset = Preset(
            signal_chain_block_id=block.id,
            name=f"Scooped_{suffix}",
            params={"low": 5, "mid": -8, "high": 3},
        )
        session.add(preset)
        await session.commit()

        # Query back
        result = await session.execute(select(Preset).where(Preset.name == f"Scooped_{suffix}"))
        saved = result.scalar_one()

        assert saved.name == f"Scooped_{suffix}"
        assert saved.params == {"low": 5, "mid": -8, "high": 3}
        assert saved.signal_chain_block_id == block.id

    async def test_preset_has_relationship_to_signal_chain_block(
        self, session: AsyncSession
    ) -> None:
        """Preset should have relationship to SignalChainBlock."""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        from gts.domain.value_objects.block_category import BlockCategory
        from gts.domain.value_objects.signal_chain_enums import Platform
        from webapp.adapters.persistence.models.block_type import BlockType
        from webapp.adapters.persistence.models.preset import Preset
        from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
        from webapp.adapters.persistence.models.user import User

        suffix = uuid.uuid4().hex[:8]
        # Create chain with block
        user = User(
            username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
        )
        session.add(user)
        await session.commit()

        chain = SignalChain(
            user_id=user.id,
            name="Test Chain",
            platform=Platform.NAM,
        )
        session.add(chain)
        await session.commit()

        block_type = BlockType(
            name=f"Delay_{suffix}",
            category=BlockCategory.DELAY,
            default_params={},
        )
        session.add(block_type)
        await session.commit()

        block = SignalChainBlock(
            signal_chain_id=chain.id,
            position=0,
            block_type_id=block_type.id,
        )
        session.add(block)
        await session.commit()

        # Create preset
        preset = Preset(
            signal_chain_block_id=block.id,
            name=f"Short Delay_{suffix}",
            params={"time": 250, "feedback": 0.3},
        )
        session.add(preset)
        await session.commit()

        # Query with joinedload to eagerly load the relationship
        result = await session.execute(
            select(Preset)
            .where(Preset.id == preset.id)
            .options(joinedload(Preset.signal_chain_block))
        )
        loaded_preset = result.unique().scalar_one()

        # Verify relationship
        assert hasattr(loaded_preset, "signal_chain_block")
        assert loaded_preset.signal_chain_block is not None
        assert loaded_preset.signal_chain_block.id == block.id

    async def test_preset_cascades_on_block_delete(self, session: AsyncSession) -> None:
        """Preset should be deleted when its SignalChainBlock is deleted."""
        from sqlalchemy import select

        from gts.domain.value_objects.block_category import BlockCategory
        from gts.domain.value_objects.signal_chain_enums import Platform
        from webapp.adapters.persistence.models.block_type import BlockType
        from webapp.adapters.persistence.models.preset import Preset
        from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
        from webapp.adapters.persistence.models.user import User

        suffix = uuid.uuid4().hex[:8]
        # Create chain with block and preset
        user = User(
            username=f"testuser_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@example.com"
        )
        session.add(user)
        await session.commit()

        chain = SignalChain(
            user_id=user.id,
            name="Test Chain",
            platform=Platform.NAM,
        )
        session.add(chain)
        await session.commit()

        block_type = BlockType(
            name=f"Reverb_{suffix}",
            category=BlockCategory.REVERB,
            default_params={},
        )
        session.add(block_type)
        await session.commit()

        block = SignalChainBlock(
            signal_chain_id=chain.id,
            position=0,
            block_type_id=block_type.id,
        )
        session.add(block)
        await session.commit()

        preset = Preset(
            signal_chain_block_id=block.id,
            name=f"Large Hall_{suffix}",
            params={"size": 1.0, "mix": 0.4},
        )
        session.add(preset)
        await session.commit()

        preset_id = preset.id

        # Delete the block
        await session.delete(block)
        await session.commit()

        # Verify preset was cascade deleted
        result = await session.execute(select(Preset).where(Preset.id == preset_id))
        assert result.scalar_one_or_none() is None
