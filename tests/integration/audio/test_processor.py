"""Integration tests for PedalboardAudioProcessor.

Tests the complete audio processing pipeline with real audio files.
"""

from pathlib import Path

import pytest

from audio.processing.processor import PedalboardAudioProcessor
from core.domain.value_objects.tone_config import ToneConfig


@pytest.fixture
def processor() -> PedalboardAudioProcessor:
    """Create a processor instance for testing."""
    return PedalboardAudioProcessor()


@pytest.fixture
def test_audio_dir(tmp_path: Path) -> Path:
    """Create temporary directory for test audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    return audio_dir


@pytest.fixture
def test_di_file(test_audio_dir: Path) -> Path:
    """Create a test DI audio file."""
    import numpy as np
    import soundfile as sf

    # Create a simple sine wave test file
    sample_rate = 48000
    duration = 1.0  # 1 second
    frequency = 440.0  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t) * 0.5  # 50% amplitude to avoid clipping

    di_path = test_audio_dir / "test_di.wav"
    sf.write(di_path, audio, sample_rate)
    return di_path


@pytest.fixture
def test_nam_model(test_audio_dir: Path) -> Path:
    """Create a test NAM model file.

    Note: This creates a minimal PyTorch checkpoint for testing.
    Real NAM models would have more complex architectures.
    """
    import torch

    # Create a minimal model checkpoint
    model_state = {
        "model": {"weight": torch.randn(1, 1), "bias": torch.randn(1)},
        "sample_rate": 48000,
    }

    model_path = test_audio_dir / "test_model.nam"
    torch.save(model_state, model_path)
    return model_path


@pytest.fixture
def test_ir_file(test_audio_dir: Path) -> Path:
    """Create a test IR file."""
    import numpy as np
    import soundfile as sf

    # Create a simple impulse response (short decay)
    sample_rate = 48000
    duration = 0.1  # 100ms

    t = np.linspace(0, duration, int(sample_rate * duration))
    ir = np.exp(-20 * t) * np.random.randn(len(t)) * 0.1  # Decaying noise

    ir_path = test_audio_dir / "test_ir.wav"
    sf.write(ir_path, ir, sample_rate)
    return ir_path


class TestGetSupportedFormats:
    """Tests for format support queries."""

    @pytest.mark.asyncio
    async def test_get_supported_formats_returns_list(
        self, processor: PedalboardAudioProcessor
    ) -> None:
        """Test that get_supported_formats returns a list of formats."""
        formats = processor.get_supported_formats()

        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "wav" in formats
        assert "flac" in formats

    @pytest.mark.asyncio
    async def test_is_format_supported_wav(self, processor: PedalboardAudioProcessor) -> None:
        """Test that WAV format is supported."""
        assert processor.is_format_supported("wav") is True

    @pytest.mark.asyncio
    async def test_is_format_supported_flac(self, processor: PedalboardAudioProcessor) -> None:
        """Test that FLAC format is supported."""
        assert processor.is_format_supported("flac") is True

    @pytest.mark.asyncio
    async def test_is_format_supported_unknown(self, processor: PedalboardAudioProcessor) -> None:
        """Test that unknown formats are not supported."""
        assert processor.is_format_supported("xyz") is False


class TestExtractWaveform:
    """Tests for waveform extraction."""

    @pytest.mark.asyncio
    async def test_extract_waveform_returns_waveform_data(
        self, processor: PedalboardAudioProcessor, test_di_file: Path
    ) -> None:
        """Test that extract_waveform returns valid WaveformData."""
        waveform = await processor.extract_waveform(test_di_file)

        assert waveform.peak_count == 200  # Default num_peaks
        assert waveform.sample_rate == 48000
        assert waveform.duration_seconds == pytest.approx(1.0, rel=0.01)
        assert all(-1.0 <= p <= 1.0 for p in waveform.peaks)

    @pytest.mark.asyncio
    async def test_extract_waveform_custom_peaks(
        self, processor: PedalboardAudioProcessor, test_di_file: Path
    ) -> None:
        """Test that extract_waveform respects num_peaks parameter."""
        waveform = await processor.extract_waveform(test_di_file, num_peaks=100)

        assert waveform.peak_count == 100


class TestMeasureLoudness:
    """Tests for loudness measurement."""

    @pytest.mark.asyncio
    async def test_measure_loudness_returns_tuple(
        self, processor: PedalboardAudioProcessor, test_di_file: Path
    ) -> None:
        """Test that measure_loudness returns (lufs, peak_dbfs) tuple."""
        lufs, peak_dbfs = await processor.measure_loudness(test_di_file)

        assert isinstance(lufs, float)
        assert isinstance(peak_dbfs, float)
        # Peak should be close to -6 dBFS for 50% amplitude signal
        assert peak_dbfs == pytest.approx(-6.0, abs=1.0)
        # LUFS should be negative (below 0)
        assert lufs < 0


class TestNormalizeLoudness:
    """Tests for loudness normalization."""

    @pytest.mark.asyncio
    async def test_normalize_loudness_creates_output(
        self, processor: PedalboardAudioProcessor, test_di_file: Path, test_audio_dir: Path
    ) -> None:
        """Test that normalize_loudness creates an output file."""
        output_path = test_audio_dir / "normalized.wav"

        result = await processor.normalize_loudness(test_di_file, output_path)

        assert output_path.exists()
        assert result.output_path == output_path
        assert result.lufs_integrated == pytest.approx(-14.0, abs=0.5)

    @pytest.mark.asyncio
    async def test_normalize_loudness_custom_target(
        self, processor: PedalboardAudioProcessor, test_di_file: Path, test_audio_dir: Path
    ) -> None:
        """Test that normalize_loudness respects custom target LUFS."""
        output_path = test_audio_dir / "normalized.wav"

        result = await processor.normalize_loudness(test_di_file, output_path, target_lufs=-12.0)

        assert result.lufs_integrated == pytest.approx(-12.0, abs=0.5)


class TestProcessDITrack:
    """Tests for complete DI track processing."""

    @pytest.mark.asyncio
    async def test_process_di_track_basic(
        self,
        processor: PedalboardAudioProcessor,
        test_di_file: Path,
        test_nam_model: Path,
        test_audio_dir: Path,
    ) -> None:
        """Test basic DI track processing through NAM model."""
        output_path = test_audio_dir / "processed.wav"
        config = ToneConfig(
            nam_model_path=test_nam_model,
            sample_rate=48000,
        )

        result = await processor.process_di_track(test_di_file, output_path, config)

        assert output_path.exists()
        assert result.output_path == output_path
        assert result.sample_rate == 48000
        assert result.duration_seconds == pytest.approx(1.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_process_di_track_with_ir(
        self,
        processor: PedalboardAudioProcessor,
        test_di_file: Path,
        test_nam_model: Path,
        test_ir_file: Path,
        test_audio_dir: Path,
    ) -> None:
        """Test DI track processing with IR convolution."""
        output_path = test_audio_dir / "processed_ir.wav"
        config = ToneConfig(
            nam_model_path=test_nam_model,
            ir_path=test_ir_file,
            sample_rate=48000,
        )

        result = await processor.process_di_track(test_di_file, output_path, config)

        assert output_path.exists()
        assert result.output_path == output_path
