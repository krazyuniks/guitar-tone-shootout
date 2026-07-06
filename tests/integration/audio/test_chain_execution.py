"""Integration tests for signal chain execution.

Tests block-by-block sequential processing with proper ordering and constraint
enforcement (FULL_RIG vs HEAD).
"""

import json
import sys
import types
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
import soundfile as sf

from audio.processing.chain_executor import (
    ChainExecutionError,
    execute_signal_chain,
)
from audio.processing.nam_loader import clear_model_cache
from gts.domain.entities.signal_chain import SignalChain, SignalChainBlock
from gts.domain.value_objects.signal_chain_enums import GearType, Platform


def _create_minimal_nam_file(path: Path) -> None:
    """Create a minimal valid .nam file (WaveNet architecture)."""
    for mod_name in ("nam.train", "nam.train.colab"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    from nam.models.wavenet import WaveNet

    layer_config = {
        "input_size": 1,
        "condition_size": 1,
        "head_size": 1,
        "channels": 1,
        "kernel_size": 2,
        "dilations": [1],
        "activation": "Tanh",
        "gated": False,
        "head_bias": False,
    }
    wavenet_config = {
        "layers": [layer_config],
        "head": None,
        "head_scale": 0.02,
    }

    model = WaveNet(
        layers_configs=wavenet_config["layers"],
        head_config=wavenet_config["head"],
        head_scale=wavenet_config["head_scale"],
        sample_rate=48000,
    )
    weights = []
    for p in model.parameters():
        weights.extend(p.detach().cpu().numpy().flatten().tolist())

    config = {
        "version": "0.5.4",
        "architecture": "WaveNet",
        "config": wavenet_config,
        "weights": weights,
        "sample_rate": 48000,
        "metadata": {},
    }

    with open(path, "w") as f:
        json.dump(config, f)


@pytest.fixture(autouse=True)
def _clear_nam_cache() -> None:
    """Clear NAM model cache between tests."""
    clear_model_cache()


@pytest.fixture
def test_audio_dir(tmp_path: Path) -> Path:
    """Create temporary directory for test audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    return audio_dir


@pytest.fixture
def test_di_file(test_audio_dir: Path) -> Path:
    """Create a test DI audio file."""
    sample_rate = 48000
    duration = 1.0
    frequency = 440.0

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t) * 0.5

    di_path = test_audio_dir / "test_di.wav"
    sf.write(di_path, audio, sample_rate)
    return di_path


@pytest.fixture
def test_nam_model(test_audio_dir: Path) -> Path:
    """Create a test NAM model (.nam JSON format)."""
    model_path = test_audio_dir / "test_model.nam"
    _create_minimal_nam_file(model_path)
    return model_path


@pytest.fixture
def test_ir_file(test_audio_dir: Path) -> Path:
    """Create a test IR file."""
    # Create a simple impulse response (short decay)
    sample_rate = 48000
    duration = 0.1  # 100ms

    t = np.linspace(0, duration, int(sample_rate * duration))
    ir = np.exp(-20 * t) * np.random.randn(len(t)) * 0.1  # Decaying noise

    ir_path = test_audio_dir / "test_ir.wav"
    sf.write(ir_path, ir, sample_rate)
    return ir_path


@pytest.fixture
def di_audio(test_di_file: Path) -> tuple[np.ndarray, int]:
    """Load test DI track."""
    audio, sample_rate = sf.read(test_di_file)
    return audio, sample_rate


@pytest.fixture
def signal_chain_with_amp_and_ir() -> SignalChain:
    """Create a signal chain with AMP + IR (HEAD configuration)."""
    chain = SignalChain(
        user_id=uuid4(),
        name="Test Chain - Head + IR",
        platform=Platform.NAM,
    )

    # Add AMP block
    amp_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    )
    chain.add_block(amp_block)

    # Add IR block
    ir_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    )
    chain.add_block(ir_block)

    return chain


@pytest.fixture
def signal_chain_with_full_rig() -> SignalChain:
    """Create a signal chain with FULL_RIG (baked-in IR)."""
    chain = SignalChain(
        user_id=uuid4(),
        name="Test Chain - Full Rig",
        platform=Platform.NAM,
    )

    # Add FULL_RIG block
    full_rig_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.FULL_RIG,
    )
    chain.add_block(full_rig_block)

    return chain


@pytest.fixture
def signal_chain_with_pre_and_post_effects() -> SignalChain:
    """Create a complete signal chain: PRE -> AMP -> IR -> POST."""
    chain = SignalChain(
        user_id=uuid4(),
        name="Test Chain - Complete",
        platform=Platform.NAM,
    )

    # Add PRE pedal block
    pre_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.PEDAL,
    )
    chain.add_block(pre_block)

    # Add AMP block
    amp_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    )
    chain.add_block(amp_block)

    # Add IR block
    ir_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=2,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    )
    chain.add_block(ir_block)

    # Add POST effect block
    post_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=3,
        user_gear_id=uuid4(),
        gear_type=GearType.POST_EFFECT,
    )
    chain.add_block(post_block)

    return chain


@pytest.fixture
def gear_path_resolver(test_nam_model: Path, test_ir_file: Path) -> Callable[[str, GearType], Path]:
    """Resolver that maps user_gear_id to actual file paths."""

    def resolver(user_gear_id: str, gear_type: GearType) -> Path:
        """Map user gear ID to file path based on gear type."""
        if gear_type in (GearType.AMP, GearType.FULL_RIG):
            return test_nam_model
        elif gear_type == GearType.IR:
            return test_ir_file
        elif gear_type in (GearType.PEDAL, GearType.POST_EFFECT):
            # For now, use same NAM model for pedals/effects
            return test_nam_model
        else:
            raise ValueError(f"Unknown gear type: {gear_type}")

    return resolver


@pytest.mark.asyncio
async def test_execute_head_configuration(
    signal_chain_with_amp_and_ir: SignalChain,
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test execution of HEAD configuration (AMP + IR)."""
    audio, sample_rate = di_audio
    chain = signal_chain_with_amp_and_ir

    # Execute chain
    result_audio = execute_signal_chain(
        chain=chain,
        di_audio=audio,
        sample_rate=sample_rate,
        gear_path_resolver=gear_path_resolver,
    )

    # Verify output
    assert result_audio is not None
    assert isinstance(result_audio, np.ndarray)
    assert len(result_audio) > 0
    assert result_audio.shape == audio.shape  # Same length


@pytest.mark.asyncio
async def test_execute_full_rig_configuration(
    signal_chain_with_full_rig: SignalChain,
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test execution of FULL_RIG configuration (no IR)."""
    audio, sample_rate = di_audio
    chain = signal_chain_with_full_rig

    # Execute chain
    result_audio = execute_signal_chain(
        chain=chain,
        di_audio=audio,
        sample_rate=sample_rate,
        gear_path_resolver=gear_path_resolver,
    )

    # Verify output
    assert result_audio is not None
    assert isinstance(result_audio, np.ndarray)
    assert len(result_audio) > 0


@pytest.mark.asyncio
async def test_execute_complete_chain(
    signal_chain_with_pre_and_post_effects: SignalChain,
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test execution of complete chain with pre/post effects."""
    audio, sample_rate = di_audio
    chain = signal_chain_with_pre_and_post_effects

    # Execute chain
    result_audio = execute_signal_chain(
        chain=chain,
        di_audio=audio,
        sample_rate=sample_rate,
        gear_path_resolver=gear_path_resolver,
    )

    # Verify output
    assert result_audio is not None
    assert isinstance(result_audio, np.ndarray)
    assert len(result_audio) > 0


@pytest.mark.asyncio
async def test_full_rig_with_ir_raises_error(
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test that FULL_RIG with IR raises ChainExecutionError."""
    audio, sample_rate = di_audio

    # Create invalid chain: FULL_RIG + IR (violates constraint)
    chain = SignalChain(
        user_id=uuid4(),
        name="Invalid Chain - Full Rig + IR",
        platform=Platform.NAM,
    )

    # Add FULL_RIG block
    full_rig_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.FULL_RIG,
    )
    chain.add_block(full_rig_block)

    # Add IR block (INVALID)
    ir_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=uuid4(),
        gear_type=GearType.IR,
    )
    chain.add_block(ir_block)

    # Should raise error
    with pytest.raises(ChainExecutionError, match=r"FULL_RIG.*cannot.*IR"):
        execute_signal_chain(
            chain=chain,
            di_audio=audio,
            sample_rate=sample_rate,
            gear_path_resolver=gear_path_resolver,
        )


@pytest.mark.asyncio
async def test_amp_without_ir_raises_error(
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test that AMP without IR raises ChainExecutionError."""
    audio, sample_rate = di_audio

    # Create invalid chain: AMP without IR (violates HEAD constraint)
    chain = SignalChain(
        user_id=uuid4(),
        name="Invalid Chain - AMP without IR",
        platform=Platform.NAM,
    )

    # Add AMP block without IR
    amp_block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=uuid4(),
        gear_type=GearType.AMP,
    )
    chain.add_block(amp_block)

    # Should raise error
    with pytest.raises(ChainExecutionError, match=r"AMP.*requires.*IR"):
        execute_signal_chain(
            chain=chain,
            di_audio=audio,
            sample_rate=sample_rate,
            gear_path_resolver=gear_path_resolver,
        )


@pytest.mark.asyncio
async def test_blocks_execute_in_position_order(
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test that blocks execute in position order (0, 1, 2, ...)."""
    audio, sample_rate = di_audio

    # Create chain with out-of-order positions
    chain = SignalChain(
        user_id=uuid4(),
        name="Test Chain - Ordering",
        platform=Platform.NAM,
    )

    # Manually create blocks with specific positions
    blocks = [
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain.id,
            position=0,
            user_gear_id=uuid4(),
            gear_type=GearType.PEDAL,
        ),
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain.id,
            position=1,
            user_gear_id=uuid4(),
            gear_type=GearType.AMP,
        ),
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain.id,
            position=2,
            user_gear_id=uuid4(),
            gear_type=GearType.IR,
        ),
    ]

    # Add in random order to test sorting
    for block in reversed(blocks):
        chain.blocks.append(block)

    # Execute - should process in position order regardless of list order
    result_audio = execute_signal_chain(
        chain=chain,
        di_audio=audio,
        sample_rate=sample_rate,
        gear_path_resolver=gear_path_resolver,
    )

    assert result_audio is not None


@pytest.mark.asyncio
async def test_empty_chain_raises_error(
    di_audio: tuple[np.ndarray, int],
    gear_path_resolver: Callable[[str, GearType], Path],
) -> None:
    """Test that empty chain raises ChainExecutionError."""
    audio, sample_rate = di_audio

    # Create empty chain
    chain = SignalChain(
        user_id=uuid4(),
        name="Empty Chain",
        platform=Platform.NAM,
    )

    # Should raise error
    with pytest.raises(ChainExecutionError, match=r"empty|no blocks"):
        execute_signal_chain(
            chain=chain,
            di_audio=audio,
            sample_rate=sample_rate,
            gear_path_resolver=gear_path_resolver,
        )
