"""Tests for audio processing functions."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from guitar_tone_shootout.audio import (
    AudioProcessingError,
    create_effect,
    load_audio,
    load_ir,
    load_nam_model,
    save_audio,
)


class TestLoadAudio:
    """Tests for load_audio function."""

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(AudioProcessingError, match="Failed to load audio"):
            load_audio(Path("/nonexistent/file.wav"))

    def test_load_valid_audio(self) -> None:
        # Create a simple WAV-like file using pedalboard
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Create test audio using pedalboard
            from pedalboard.io import AudioFile

            test_audio = np.random.randn(1, 44100).astype(np.float32) * 0.5
            with AudioFile(str(temp_path), "w", samplerate=44100, num_channels=1) as af:
                af.write(test_audio)

            audio, sample_rate = load_audio(temp_path)

            assert sample_rate == 44100
            assert audio.ndim == 1  # Should be mono
            assert len(audio) == 44100
        finally:
            temp_path.unlink(missing_ok=True)


class TestSaveAudio:
    """Tests for save_audio function."""

    def test_save_mono_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.flac"
            test_audio = np.random.randn(44100).astype(np.float32) * 0.5

            result = save_audio(test_audio, output_path, 44100)

            assert result == output_path
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "test.flac"
            test_audio = np.random.randn(1000).astype(np.float32)

            result = save_audio(test_audio, output_path, 44100)

            assert result.exists()


class TestLoadNAMModel:
    """Tests for load_nam_model function."""

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(AudioProcessingError, match="NAM model not found"):
            load_nam_model(Path("/nonexistent/model.nam"))

    def test_invalid_json_raises(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".nam", delete=False) as f:
            f.write(b"not valid json")
            temp_path = Path(f.name)

        try:
            with pytest.raises(AudioProcessingError, match="Failed to load NAM model"):
                load_nam_model(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)


class TestLoadIR:
    """Tests for load_ir function."""

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(AudioProcessingError, match="IR file not found"):
            load_ir(Path("/nonexistent/ir.wav"))

    def test_load_valid_ir(self) -> None:
        # Create a simple IR file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            from pedalboard.io import AudioFile

            # Create impulse response (simple impulse)
            ir_data = np.zeros((1, 4096), dtype=np.float32)
            ir_data[0, 0] = 1.0  # Delta function

            with AudioFile(str(temp_path), "w", samplerate=48000, num_channels=1) as af:
                af.write(ir_data)

            convolution = load_ir(temp_path)

            assert convolution is not None
        finally:
            temp_path.unlink(missing_ok=True)


class TestCreateEffect:
    """Tests for create_effect function."""

    def test_gain_effect(self) -> None:
        effect = create_effect("gain", "3.0")
        assert effect is not None

    def test_gain_invalid_value(self) -> None:
        effect = create_effect("gain", "not_a_number")
        assert effect is None

    def test_eq_highpass(self) -> None:
        effect = create_effect("eq", "highpass_80hz")
        assert effect is not None

    def test_eq_unknown_preset(self) -> None:
        effect = create_effect("eq", "unknown_preset")
        assert effect is None

    def test_reverb_room(self) -> None:
        effect = create_effect("reverb", "room")
        assert effect is not None

    def test_reverb_hall(self) -> None:
        effect = create_effect("reverb", "hall")
        assert effect is not None

    def test_delay_slapback(self) -> None:
        effect = create_effect("delay", "slapback")
        assert effect is not None

    def test_unknown_effect_type(self) -> None:
        effect = create_effect("unknown_type", "value")
        assert effect is None
