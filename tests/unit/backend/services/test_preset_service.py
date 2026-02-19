"""Unit tests for PresetService.

Tests the service layer for managing parameter presets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from core.domain.value_objects.block_category import BlockCategory
from webapp.adapters.persistence.models.block_type import BlockType
from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username=f"testuser_{uuid4().hex[:8]}",
        email=f"test_{uuid4().hex[:8]}@example.com",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_block_type(session: AsyncSession) -> BlockType:
    """Create a test block type."""
    block_type = BlockType(
        id=uuid4(),
        name=f"Test Compressor {uuid4().hex[:8]}",
        category=BlockCategory.DYNAMICS,
        default_params={
            "threshold": -20.0,
            "ratio": 4.0,
            "attack": 5.0,
            "release": 50.0,
        },
    )
    session.add(block_type)
    await session.commit()
    await session.refresh(block_type)
    return block_type


@pytest.fixture
async def test_signal_chain(session: AsyncSession, test_user: User) -> SignalChain:
    """Create a test signal chain."""
    from core.domain.value_objects.signal_chain_enums import Platform

    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name=f"Test Chain {uuid4().hex[:8]}",
        description="Test chain for presets",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()
    await session.refresh(chain)
    return chain


@pytest.fixture
async def test_signal_chain_block(
    session: AsyncSession,
    test_signal_chain: SignalChain,
    test_block_type: BlockType,
) -> SignalChainBlock:
    """Create a test signal chain block."""
    block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=test_signal_chain.id,
        block_type_id=test_block_type.id,
        position=1,
        params={
            "threshold": -15.0,
            "ratio": 3.0,
        },
    )
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


class TestPresetService:
    """Tests for PresetService parameter management."""

    async def test_service_exists(self) -> None:
        """Verify PresetService can be imported."""
        from webapp.services.preset_service import PresetService

        assert PresetService is not None

    async def test_service_saves_preset(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can save a preset for a signal chain block."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Save a preset with custom parameters
        preset = await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Heavy Compression",
            params={
                "threshold": -30.0,
                "ratio": 8.0,
                "attack": 2.0,
                "release": 100.0,
            },
        )

        assert preset is not None
        assert preset.id is not None
        assert preset.signal_chain_block_id == test_signal_chain_block.id
        assert preset.name == "Heavy Compression"
        assert preset.params["threshold"] == -30.0
        assert preset.params["ratio"] == 8.0

    async def test_service_loads_preset(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can load a preset by ID."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Save a preset first
        saved = await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Test Preset",
            params={"threshold": -25.0},
        )

        # Load it back
        loaded = await service.load_preset(saved.id)

        assert loaded is not None
        assert loaded.id == saved.id
        assert loaded.name == "Test Preset"
        assert loaded.params["threshold"] == -25.0

    async def test_service_lists_presets_for_block(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can list all presets for a signal chain block."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Create multiple presets
        await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Preset 1",
            params={"threshold": -10.0},
        )
        await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Preset 2",
            params={"threshold": -20.0},
        )

        # List all presets for this block
        presets = await service.list_presets_for_block(test_signal_chain_block.id)

        assert presets is not None
        assert len(presets) == 2
        assert {p.name for p in presets} == {"Preset 1", "Preset 2"}

    async def test_service_deletes_preset(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can delete a preset."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Save a preset
        preset = await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="To Delete",
            params={"threshold": -15.0},
        )

        preset_id = preset.id

        # Delete it
        await service.delete_preset(preset_id)

        # Verify it's gone
        loaded = await service.load_preset(preset_id)
        assert loaded is None

    async def test_service_validates_preset_name(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service validates preset name is not empty."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Empty name should raise error
        with pytest.raises(ValueError, match="Preset name cannot be empty"):
            await service.save_preset(
                signal_chain_block_id=test_signal_chain_block.id,
                name="",
                params={},
            )

    async def test_service_validates_block_exists(
        self,
        session: AsyncSession,
    ) -> None:
        """Test service validates signal chain block exists."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Non-existent block should raise error
        fake_block_id = uuid4()
        with pytest.raises(ValueError, match="Signal chain block .* not found"):
            await service.save_preset(
                signal_chain_block_id=fake_block_id,
                name="Test",
                params={},
            )

    async def test_service_updates_existing_preset(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can update an existing preset."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Save initial preset
        preset = await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Original",
            params={"threshold": -10.0},
        )

        preset_id = preset.id

        # Update it
        updated = await service.update_preset(
            preset_id=preset_id,
            name="Updated",
            params={"threshold": -25.0, "ratio": 6.0},
        )

        assert updated is not None
        assert updated.id == preset_id
        assert updated.name == "Updated"
        assert updated.params["threshold"] == -25.0
        assert updated.params["ratio"] == 6.0

    async def test_service_applies_preset_to_block(
        self,
        session: AsyncSession,
        test_signal_chain_block: SignalChainBlock,
    ) -> None:
        """Test service can apply a preset's parameters to a block."""
        from webapp.services.preset_service import PresetService

        service = PresetService(session)

        # Save a preset
        preset = await service.save_preset(
            signal_chain_block_id=test_signal_chain_block.id,
            name="Apply Test",
            params={
                "threshold": -35.0,
                "ratio": 10.0,
                "attack": 1.0,
            },
        )

        # Apply the preset to the block
        await service.apply_preset_to_block(
            preset_id=preset.id,
            signal_chain_block_id=test_signal_chain_block.id,
        )

        # Verify the block's params were updated
        await session.refresh(test_signal_chain_block)
        assert test_signal_chain_block.params["threshold"] == -35.0
        assert test_signal_chain_block.params["ratio"] == 10.0
        assert test_signal_chain_block.params["attack"] == 1.0
