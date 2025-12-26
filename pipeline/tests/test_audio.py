"""Tests for audio processing functions."""

from pathlib import Path

import numpy as np
import pytest
from pedalboard.io import AudioFile

from guitar_tone_shootout.audio import (
    AudioProcessingError,
    create_effect,
    load_audio,
    load_ir,
    load_nam_model,
    process_chain,
    save_audio,
)
from guitar_tone_shootout.config import ChainEffect

# =============================================================================
# Audio I/O Tests
# =============================================================================


def test_load_audio(tmp_path: Path) -> None:
    # Create a test WAV file
    audio_path = tmp_path / "test.wav"
    test_audio = np.random.randn(1, 44100).astype(np.float32) * 0.5
    with AudioFile(str(audio_path), "w", samplerate=44100, num_channels=1) as af:
        af.write(test_audio)

    audio, sample_rate = load_audio(audio_path)

    assert sample_rate == 44100
    assert audio.ndim == 1  # Should be mono
    assert len(audio) == 44100
    assert audio.dtype == np.float32


def test_load_audio_missing_raises() -> None:
    with pytest.raises(AudioProcessingError, match="Failed to load audio"):
        load_audio(Path("/nonexistent/file.wav"))


def test_save_audio(tmp_path: Path) -> None:
    output_path = tmp_path / "test.flac"
    test_audio = np.random.randn(44100).astype(np.float32) * 0.5

    result = save_audio(test_audio, output_path, 44100)

    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_save_audio_creates_parent_dirs(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "dir" / "test.flac"
    test_audio = np.random.randn(1000).astype(np.float32)

    result = save_audio(test_audio, output_path, 44100)

    assert result.exists()


def test_save_and_reload_lossless(tmp_path: Path) -> None:
    """FLAC round-trip should preserve audio data."""
    output_path = tmp_path / "test.flac"
    original = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100)).astype(np.float32)

    save_audio(original, output_path, 44100)
    reloaded, sr = load_audio(output_path)

    assert sr == 44100
    assert len(reloaded) == len(original)
    np.testing.assert_allclose(original, reloaded, rtol=0.05, atol=1e-4)


# =============================================================================
# IR Loading Tests
# =============================================================================


def test_load_ir(tmp_path: Path) -> None:
    # Create a simple IR file (impulse)
    ir_path = tmp_path / "test_ir.wav"
    ir_data = np.zeros((1, 4096), dtype=np.float32)
    ir_data[0, 0] = 1.0  # Delta function
    with AudioFile(str(ir_path), "w", samplerate=48000, num_channels=1) as af:
        af.write(ir_data)

    convolution = load_ir(ir_path)

    assert convolution is not None


def test_load_ir_missing_raises() -> None:
    with pytest.raises(AudioProcessingError, match="IR file not found"):
        load_ir(Path("/nonexistent/ir.wav"))


# =============================================================================
# NAM Model Tests
# =============================================================================


def test_load_nam_model_missing_raises() -> None:
    with pytest.raises(AudioProcessingError, match="NAM model not found"):
        load_nam_model(Path("/nonexistent/model.nam"))


def test_load_nam_model_invalid_json_raises(tmp_path: Path) -> None:
    model_path = tmp_path / "bad.nam"
    model_path.write_text("not valid json")

    with pytest.raises(AudioProcessingError, match="Failed to load NAM model"):
        load_nam_model(model_path)


# =============================================================================
# Effect Creation Tests
# =============================================================================


@pytest.mark.parametrize(
    ("effect_type", "value"),
    [
        ("gain", "3.0"),
        ("gain", "-6.0"),
        ("eq", "highpass_80hz"),
        ("eq", "lowpass_12k"),
        ("reverb", "room"),
        ("reverb", "hall"),
        ("delay", "slapback"),
    ],
)
def test_create_effect_valid(effect_type: str, value: str) -> None:
    effect = create_effect(effect_type, value)
    assert effect is not None


@pytest.mark.parametrize(
    ("effect_type", "value"),
    [
        ("gain", "not_a_number"),
        ("eq", "unknown_preset"),
        ("unknown_type", "value"),
    ],
)
def test_create_effect_invalid_returns_none(effect_type: str, value: str) -> None:
    effect = create_effect(effect_type, value)
    assert effect is None


# =============================================================================
# Effect Chain Processing Tests
# =============================================================================


@pytest.fixture
def sample_audio() -> np.ndarray:
    """1 second of 440Hz sine wave."""
    t = np.linspace(0, 1, 44100, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_process_chain_eq(sample_audio: np.ndarray) -> None:
    chain = [ChainEffect(effect_type="eq", value="highpass_80hz")]

    processed = process_chain(sample_audio, 44100, chain)

    assert processed is not None
    assert processed.dtype == np.float32


def test_process_chain_gain(sample_audio: np.ndarray) -> None:
    chain = [ChainEffect(effect_type="gain", value="6.0")]

    processed = process_chain(sample_audio, 44100, chain)

    # +6dB should roughly double amplitude
    assert np.max(np.abs(processed)) > np.max(np.abs(sample_audio))


def test_process_chain_reverb(sample_audio: np.ndarray) -> None:
    chain = [ChainEffect(effect_type="reverb", value="room")]

    processed = process_chain(sample_audio, 44100, chain)

    assert processed is not None
    # Reverb adds tail
    assert len(processed) >= len(sample_audio)


def test_process_chain_with_ir(sample_audio: np.ndarray, tmp_path: Path) -> None:
    # Create a test IR
    ir_path = tmp_path / "test_ir.wav"
    ir_data = np.zeros((1, 4096), dtype=np.float32)
    ir_data[0, 0] = 1.0
    with AudioFile(str(ir_path), "w", samplerate=44100, num_channels=1) as af:
        af.write(ir_data)

    chain = [ChainEffect(effect_type="ir", value=str(ir_path))]

    processed = process_chain(sample_audio, 44100, chain)

    assert processed is not None
    assert processed.dtype == np.float32


def test_process_chain_multiple_effects(sample_audio: np.ndarray, tmp_path: Path) -> None:
    # Create a test IR
    ir_path = tmp_path / "test_ir.wav"
    ir_data = np.zeros((1, 4096), dtype=np.float32)
    ir_data[0, 0] = 1.0
    with AudioFile(str(ir_path), "w", samplerate=44100, num_channels=1) as af:
        af.write(ir_data)

    chain = [
        ChainEffect(effect_type="eq", value="highpass_80hz"),
        ChainEffect(effect_type="ir", value=str(ir_path)),
        ChainEffect(effect_type="gain", value="-3.0"),
    ]

    processed = process_chain(sample_audio, 44100, chain)

    assert processed is not None
    assert processed.dtype == np.float32
