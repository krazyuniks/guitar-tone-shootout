"""Integration tests for pipeline processing with FFmpeg."""

import shutil
from pathlib import Path

import pytest

from guitar_tone_shootout.pipeline import (
    concatenate_audio,
    concatenate_clips,
    create_clip,
    trim_silence,
    trim_to_duration,
)

# Skip all tests in this module if FFmpeg is not available
pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="FFmpeg not installed",
)


class TestTrimSilence:
    """Integration tests for audio trimming with FFmpeg."""

    def test_trim_silence_real_file(self, test_di_track: Path) -> None:
        """Test trimming silence from real audio file."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        trimmed = trim_silence(test_di_track)

        assert trimmed.exists()
        assert trimmed.stat().st_size > 0
        # Clean up temp file
        trimmed.unlink(missing_ok=True)

    def test_trim_to_duration(self, test_di_track: Path) -> None:
        """Test trimming to specific duration."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        trimmed = trim_to_duration(test_di_track, duration=1.0)

        assert trimmed.exists()
        # File should be smaller than original (1s vs 2s)
        assert trimmed.stat().st_size < test_di_track.stat().st_size
        # Clean up
        trimmed.unlink(missing_ok=True)


class TestClipCreation:
    """Integration tests for video clip creation with FFmpeg."""

    def test_create_clip_from_image_and_audio(self, test_di_track: Path, tmp_path: Path) -> None:
        """Test creating a video clip from image and audio."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        # Create a simple test image
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        image_path = tmp_path / "test_image.png"
        img = Image.new("RGB", (1920, 1080), color=(30, 30, 50))
        img.save(image_path)

        output_path = tmp_path / "test_clip.mp4"

        result = create_clip(
            image=image_path,
            audio=test_di_track,
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestConcatenation:
    """Integration tests for audio/video concatenation."""

    def test_concatenate_audio_files(self, test_di_track: Path, tmp_path: Path) -> None:
        """Test concatenating multiple audio files."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        # Create copies for concatenation
        audio1 = tmp_path / "audio1.wav"
        audio2 = tmp_path / "audio2.wav"
        shutil.copy(test_di_track, audio1)
        shutil.copy(test_di_track, audio2)

        output = tmp_path / "concatenated.flac"
        result = concatenate_audio([audio1, audio2], output)

        assert result == output
        assert output.exists()
        # Output file should have non-zero size
        assert output.stat().st_size > 0
        # Verify by loading and checking duration
        from guitar_tone_shootout.audio import load_audio

        original, _sr = load_audio(test_di_track)
        concatenated, _ = load_audio(output)
        # Concatenated should be approximately 2x the original length
        assert len(concatenated) >= len(original) * 1.9

    def test_concatenate_video_clips(self, test_di_track: Path, tmp_path: Path) -> None:
        """Test concatenating multiple video clips."""
        if not test_di_track.exists():
            pytest.skip("Test DI track not generated")

        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Create two test clips
        clips = []
        for i in range(2):
            # Create image
            img_path = tmp_path / f"img_{i}.png"
            img = Image.new("RGB", (1920, 1080), color=(30 + i * 20, 30, 50))
            img.save(img_path)

            # Trim audio to 1 second for faster test
            trimmed = trim_to_duration(test_di_track, 0.5)

            # Create clip
            clip_path = tmp_path / f"clip_{i}.mp4"
            create_clip(img_path, trimmed, clip_path)
            clips.append(clip_path)

            # Clean up trimmed audio
            trimmed.unlink(missing_ok=True)

        output = tmp_path / "concatenated.mp4"
        result = concatenate_clips(clips, output)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
