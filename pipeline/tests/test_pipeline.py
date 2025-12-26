"""Tests for pipeline processing functions."""

import shutil
from pathlib import Path

import numpy as np
import pytest
from pedalboard.io import AudioFile
from PIL import Image

from guitar_tone_shootout.audio import load_audio
from guitar_tone_shootout.pipeline import (
    PipelineError,
    _sanitize_filename,
    concatenate_audio,
    concatenate_clips,
    create_clip,
    trim_silence,
    trim_to_duration,
)

# =============================================================================
# Filename Sanitization Tests
# =============================================================================


@pytest.mark.parametrize(
    ("input_name", "expected"),
    [
        ("test", "test"),
        ("Test Name", "test_name"),
        ("my test name", "my_test_name"),
        ("test!@#$%name", "test_name"),
        ("test   name", "test_name"),
        ("TestName", "testname"),
        ("test-name", "test-name"),
        ("  spaced  ", "spaced"),
    ],
)
def test_sanitize_filename(input_name: str, expected: str) -> None:
    assert _sanitize_filename(input_name) == expected


# =============================================================================
# Audio Fixtures
# =============================================================================


@pytest.fixture
def test_audio_file(tmp_path: Path) -> Path:
    """Create a 2-second test audio file."""
    audio_path = tmp_path / "test.wav"
    duration = 2.0
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    with AudioFile(str(audio_path), "w", samplerate=sample_rate, num_channels=1) as af:
        af.write(audio.reshape(1, -1))

    return audio_path


@pytest.fixture
def test_image(tmp_path: Path) -> Path:
    """Create a test image."""
    image_path = tmp_path / "test.png"
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 50))
    img.save(image_path)
    return image_path


# =============================================================================
# Trim Tests
# =============================================================================


def test_trim_silence(test_audio_file: Path) -> None:
    trimmed = trim_silence(test_audio_file)

    assert trimmed.exists()
    assert trimmed.stat().st_size > 0

    # Cleanup
    trimmed.unlink(missing_ok=True)


def test_trim_silence_missing_raises() -> None:
    with pytest.raises(PipelineError, match="Audio file not found"):
        trim_silence(Path("/nonexistent/file.wav"))


def test_trim_to_duration(test_audio_file: Path) -> None:
    trimmed = trim_to_duration(test_audio_file, duration=1.0)

    assert trimmed.exists()
    # Should be smaller than 2-second original
    assert trimmed.stat().st_size < test_audio_file.stat().st_size

    # Verify approximate duration (FFmpeg may add small padding)
    audio, sr = load_audio(trimmed)
    duration_seconds = len(audio) / sr
    assert 0.9 <= duration_seconds <= 1.1

    # Cleanup
    trimmed.unlink(missing_ok=True)


# =============================================================================
# Clip Creation Tests
# =============================================================================


def test_create_clip(test_image: Path, test_audio_file: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "output.mp4"

    result = create_clip(test_image, test_audio_file, output_path)

    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_create_clip_missing_image_raises(test_audio_file: Path, tmp_path: Path) -> None:
    with pytest.raises(PipelineError, match="Image not found"):
        create_clip(
            image=Path("/nonexistent/image.png"),
            audio=test_audio_file,
            output_path=tmp_path / "output.mp4",
        )


def test_create_clip_missing_audio_raises(test_image: Path, tmp_path: Path) -> None:
    with pytest.raises(PipelineError, match="Audio not found"):
        create_clip(
            image=test_image,
            audio=Path("/nonexistent/audio.flac"),
            output_path=tmp_path / "output.mp4",
        )


# =============================================================================
# Concatenation Tests
# =============================================================================


def test_concatenate_audio(test_audio_file: Path, tmp_path: Path) -> None:
    # Create copies for concatenation
    audio1 = tmp_path / "audio1.wav"
    audio2 = tmp_path / "audio2.wav"
    shutil.copy(test_audio_file, audio1)
    shutil.copy(test_audio_file, audio2)

    output = tmp_path / "concatenated.flac"
    result = concatenate_audio([audio1, audio2], output)

    assert result == output
    assert output.exists()

    # Verify length (should be ~2x original)
    original, _ = load_audio(test_audio_file)
    concatenated, _ = load_audio(output)
    assert len(concatenated) >= len(original) * 1.9


def test_concatenate_audio_empty_raises() -> None:
    with pytest.raises(PipelineError, match="No audio files to concatenate"):
        concatenate_audio([], Path("/tmp/output.flac"))


def test_concatenate_audio_missing_raises() -> None:
    with pytest.raises(PipelineError, match="Audio file not found"):
        concatenate_audio([Path("/nonexistent.flac")], Path("/tmp/output.flac"))


def test_concatenate_clips(test_image: Path, test_audio_file: Path, tmp_path: Path) -> None:
    # Create two short clips
    clips = []
    for i in range(2):
        # Trim to 0.5s for faster test
        trimmed = trim_to_duration(test_audio_file, 0.5)
        clip_path = tmp_path / f"clip_{i}.mp4"
        create_clip(test_image, trimmed, clip_path)
        clips.append(clip_path)
        trimmed.unlink(missing_ok=True)

    output = tmp_path / "concatenated.mp4"
    result = concatenate_clips(clips, output)

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_concatenate_clips_empty_raises() -> None:
    with pytest.raises(PipelineError, match="No clips to concatenate"):
        concatenate_clips([], Path("/tmp/output.mp4"))


def test_concatenate_clips_missing_raises() -> None:
    with pytest.raises(PipelineError, match="Clip not found"):
        concatenate_clips([Path("/nonexistent.mp4")], Path("/tmp/output.mp4"))
