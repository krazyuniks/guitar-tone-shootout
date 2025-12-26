"""Tests for pipeline processing functions."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from guitar_tone_shootout.pipeline import (
    PipelineError,
    _sanitize_filename,
    concatenate_audio,
    concatenate_clips,
    create_clip,
    trim_silence,
)


class TestSanitizeFilename:
    """Tests for _sanitize_filename function."""

    def test_simple_name(self) -> None:
        assert _sanitize_filename("test") == "test"

    def test_spaces_to_underscores(self) -> None:
        assert _sanitize_filename("my test name") == "my_test_name"

    def test_special_chars_removed(self) -> None:
        assert _sanitize_filename("test!@#$%name") == "test_name"

    def test_multiple_underscores_collapsed(self) -> None:
        assert _sanitize_filename("test   name") == "test_name"

    def test_lowercase(self) -> None:
        assert _sanitize_filename("TestName") == "testname"

    def test_preserves_hyphens(self) -> None:
        assert _sanitize_filename("test-name") == "test-name"


class TestTrimSilence:
    """Tests for trim_silence function."""

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(PipelineError, match="Audio file not found"):
            trim_silence(Path("/nonexistent/file.wav"))

    @patch("guitar_tone_shootout.pipeline._run_ffmpeg")
    def test_successful_trim(self, mock_ffmpeg: MagicMock) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"RIFF" + b"\x00" * 100)

        try:
            result = trim_silence(temp_path)
            assert result.exists() or mock_ffmpeg.called
            mock_ffmpeg.assert_called_once()

            # Check FFmpeg was called with silenceremove filter
            call_args = mock_ffmpeg.call_args[0][0]
            assert any("silenceremove" in str(arg) for arg in call_args)
        finally:
            temp_path.unlink(missing_ok=True)
            if result != temp_path:
                result.unlink(missing_ok=True)


class TestCreateClip:
    """Tests for create_clip function."""

    def test_image_not_found_raises(self) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".flac") as audio,
            pytest.raises(PipelineError, match="Image not found"),
        ):
            create_clip(
                image=Path("/nonexistent/image.png"),
                audio=Path(audio.name),
                output_path=Path("/tmp/output.mp4"),
            )

    def test_audio_not_found_raises(self) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".png") as image,
            pytest.raises(PipelineError, match="Audio not found"),
        ):
            create_clip(
                image=Path(image.name),
                audio=Path("/nonexistent/audio.flac"),
                output_path=Path("/tmp/output.mp4"),
            )

    @patch("guitar_tone_shootout.pipeline._run_ffmpeg")
    def test_ffmpeg_called_correctly(self, mock_ffmpeg: MagicMock) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img,
            tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as audio,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            img_path = Path(img.name)
            audio_path = Path(audio.name)
            output_path = Path(tmpdir) / "output.mp4"

            try:
                create_clip(img_path, audio_path, output_path)

                mock_ffmpeg.assert_called_once()
                call_args = mock_ffmpeg.call_args[0][0]

                # Verify key FFmpeg arguments
                assert "-loop" in call_args
                assert "libx264" in call_args
                assert "aac" in call_args
                assert "384k" in call_args
            finally:
                img_path.unlink(missing_ok=True)
                audio_path.unlink(missing_ok=True)


class TestConcatenateClips:
    """Tests for concatenate_clips function."""

    def test_empty_list_raises(self) -> None:
        with pytest.raises(PipelineError, match="No clips to concatenate"):
            concatenate_clips([], Path("/tmp/output.mp4"))

    def test_missing_clip_raises(self) -> None:
        with pytest.raises(PipelineError, match="Clip not found"):
            concatenate_clips([Path("/nonexistent.mp4")], Path("/tmp/output.mp4"))

    @patch("guitar_tone_shootout.pipeline._run_ffmpeg")
    def test_concat_file_created(self, mock_ffmpeg: MagicMock) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip1,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip2,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            clip1_path = Path(clip1.name)
            clip2_path = Path(clip2.name)
            output_path = Path(tmpdir) / "output.mp4"

            try:
                concatenate_clips([clip1_path, clip2_path], output_path)

                mock_ffmpeg.assert_called_once()
                call_args = mock_ffmpeg.call_args[0][0]

                # Verify concat demuxer used
                assert "-f" in call_args
                assert "concat" in call_args
            finally:
                clip1_path.unlink(missing_ok=True)
                clip2_path.unlink(missing_ok=True)


class TestConcatenateAudio:
    """Tests for concatenate_audio function."""

    def test_empty_list_raises(self) -> None:
        with pytest.raises(PipelineError, match="No audio files to concatenate"):
            concatenate_audio([], Path("/tmp/output.flac"))

    def test_missing_audio_raises(self) -> None:
        with pytest.raises(PipelineError, match="Audio file not found"):
            concatenate_audio([Path("/nonexistent.flac")], Path("/tmp/output.flac"))

    @patch("guitar_tone_shootout.pipeline._run_ffmpeg")
    def test_flac_output(self, mock_ffmpeg: MagicMock) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as audio1,
            tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as audio2,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            audio1_path = Path(audio1.name)
            audio2_path = Path(audio2.name)
            output_path = Path(tmpdir) / "output.flac"

            try:
                concatenate_audio([audio1_path, audio2_path], output_path)

                mock_ffmpeg.assert_called_once()
                call_args = mock_ffmpeg.call_args[0][0]

                # Verify FLAC codec used
                assert "flac" in call_args
            finally:
                audio1_path.unlink(missing_ok=True)
                audio2_path.unlink(missing_ok=True)
