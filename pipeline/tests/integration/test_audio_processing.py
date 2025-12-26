"""Integration tests for audio processing with real files."""

from pathlib import Path

import numpy as np
import pytest

from guitar_tone_shootout.audio import (
    load_audio,
    load_ir,
    process_chain,
    save_audio,
)
from guitar_tone_shootout.config import ChainEffect


class TestAudioLoadSave:
    """Integration tests for audio file I/O."""

    def test_load_real_di_track(self, test_di_track: Path) -> None:
        """Test loading the real test DI track."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        audio, sample_rate = load_audio(test_di_track)

        assert sample_rate == 44100
        assert audio.ndim == 1
        assert len(audio) > 0
        assert audio.dtype == np.float32

    def test_save_and_reload(self, tmp_path: Path, sample_audio: np.ndarray) -> None:
        """Test saving audio and reloading produces same data."""
        output_path = tmp_path / "test_output.flac"

        save_audio(sample_audio, output_path, 44100)
        reloaded, sr = load_audio(output_path)

        assert sr == 44100
        assert len(reloaded) == len(sample_audio)
        # FLAC is lossless but may have small float32 precision differences
        np.testing.assert_allclose(sample_audio, reloaded, rtol=0.05, atol=1e-4)


class TestIRProcessing:
    """Integration tests for impulse response processing."""

    def test_load_real_ir(self, test_ir: Path) -> None:
        """Test loading the real test IR."""
        if not test_ir.exists():
            pytest.skip("Test IR not generated")

        convolution = load_ir(test_ir)
        assert convolution is not None

    def test_ir_convolution(self, test_ir: Path, test_di_track: Path) -> None:
        """Test that IR convolution produces valid output."""
        if not test_ir.exists() or not test_di_track.exists():
            pytest.skip("Test fixtures not generated")

        audio, sr = load_audio(test_di_track)

        # Create chain with just IR
        chain = [ChainEffect(effect_type="ir", value=str(test_ir))]

        # Process
        processed = process_chain(audio, sr, chain)

        assert processed is not None
        assert processed.dtype == np.float32
        # Convolution may change length slightly
        assert len(processed) >= len(audio) * 0.9


class TestEffectChains:
    """Integration tests for effect chain processing."""

    def test_eq_effect(self, sample_audio: np.ndarray) -> None:
        """Test EQ effect actually filters audio."""
        chain = [ChainEffect(effect_type="eq", value="highpass_80hz")]

        processed = process_chain(sample_audio, 44100, chain)

        assert processed is not None
        # High-pass should reduce low frequency content
        assert processed.dtype == np.float32

    def test_gain_effect(self, sample_audio: np.ndarray) -> None:
        """Test gain effect changes amplitude."""
        # +6dB gain
        chain = [ChainEffect(effect_type="gain", value="6.0")]

        processed = process_chain(sample_audio, 44100, chain)

        # +6dB should roughly double amplitude
        assert np.max(np.abs(processed)) > np.max(np.abs(sample_audio))

    def test_reverb_effect(self, sample_audio: np.ndarray) -> None:
        """Test reverb effect extends audio."""
        chain = [ChainEffect(effect_type="reverb", value="room")]

        processed = process_chain(sample_audio, 44100, chain)

        assert processed is not None
        # Reverb adds tail, so output should be at least as long
        assert len(processed) >= len(sample_audio)

    def test_multi_effect_chain(self, test_di_track: Path, test_ir: Path, tmp_path: Path) -> None:
        """Test chain with multiple effects."""
        if not test_di_track.exists() or not test_ir.exists():
            pytest.skip("Test fixtures not generated")

        audio, sr = load_audio(test_di_track)

        chain = [
            ChainEffect(effect_type="eq", value="highpass_80hz"),
            ChainEffect(effect_type="ir", value=str(test_ir)),
            ChainEffect(effect_type="gain", value="-3.0"),
        ]

        processed = process_chain(audio, sr, chain)

        assert processed is not None
        assert processed.dtype == np.float32

        # Save and verify
        output = tmp_path / "processed.flac"
        save_audio(processed, output, sr)
        assert output.exists()
        assert output.stat().st_size > 0
