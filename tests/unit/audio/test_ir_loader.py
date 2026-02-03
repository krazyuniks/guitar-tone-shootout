"""Unit tests for IR loader."""

import wave
from pathlib import Path

import pytest

from audio.processing.ir_loader import IRLoadError, load_ir


class TestIRLoader:
    """Test IR file loading."""

    @pytest.fixture
    def simple_wav_file(self, tmp_path: Path) -> Path:
        """Create a simple valid WAV file for testing."""
        wav_file = tmp_path / "test.wav"

        # Create a minimal valid WAV file (mono, 16-bit, 48kHz, 1 second)
        with wave.open(str(wav_file), "wb") as wav:
            wav.setnchannels(1)  # mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(48000)  # 48kHz
            # Write 1 second of silence (zeros)
            wav.writeframes(b"\x00\x00" * 48000)

        return wav_file

    def test_load_ir_from_wav(self, simple_wav_file: Path) -> None:
        """Test loading IR from WAV file."""
        from pedalboard import Convolution

        convolution = load_ir(simple_wav_file)

        # Verify it's a Convolution effect
        assert isinstance(convolution, Convolution)

    def test_load_ir_from_path(self, simple_wav_file: Path) -> None:
        """Test load_ir accepts Path objects."""
        from pedalboard import Convolution

        convolution = load_ir(simple_wav_file)
        assert isinstance(convolution, Convolution)

    def test_load_ir_from_string(self, simple_wav_file: Path) -> None:
        """Test load_ir accepts string paths."""
        from pedalboard import Convolution

        convolution = load_ir(str(simple_wav_file))
        assert isinstance(convolution, Convolution)

    def test_load_ir_file_not_found(self, tmp_path: Path) -> None:
        """Test loading IR from non-existent file raises IRLoadError."""
        nonexistent = tmp_path / "nonexistent.wav"

        with pytest.raises(IRLoadError, match="IR file not found"):
            load_ir(nonexistent)

    def test_load_ir_invalid_file(self, tmp_path: Path) -> None:
        """Test loading IR from invalid file raises IRLoadError."""
        # Create a file with invalid content
        invalid_file = tmp_path / "invalid.wav"
        invalid_file.write_text("not a valid audio file")

        with pytest.raises(IRLoadError, match="Failed to load IR"):
            load_ir(invalid_file)

    def test_load_ir_empty_file(self, tmp_path: Path) -> None:
        """Test loading IR from empty file raises IRLoadError."""
        empty_file = tmp_path / "empty.wav"
        empty_file.write_bytes(b"")

        with pytest.raises(IRLoadError, match="Failed to load IR"):
            load_ir(empty_file)
