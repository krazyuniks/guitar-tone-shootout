"""Unit tests for audio package cleanup.

Verifies that:
- model/audio/src/audio/video/ stub is removed
- moviepy dependency is removed from model/audio/pyproject.toml
"""

from pathlib import Path

import pytest


class TestAudioCleanup:
    """Test audio package cleanup (video stub and moviepy removed)."""

    @pytest.fixture
    def audio_root(self) -> Path:
        """Path to model/audio/ directory."""
        return Path("model/audio")

    @pytest.fixture
    def audio_src(self, audio_root: Path) -> Path:
        """Path to model/audio/src/audio/ directory."""
        return audio_root / "src" / "audio"

    def test_video_stub_removed(self, audio_src: Path) -> None:
        """model/audio/src/audio/video/ stub directory removed."""
        video_stub = audio_src / "video"
        assert not video_stub.exists(), "model/audio/src/audio/video/ stub must be removed"

    def test_moviepy_dependency_removed(self, audio_root: Path) -> None:
        """moviepy dependency removed from model/audio/pyproject.toml."""
        pyproject = audio_root / "pyproject.toml"
        content = pyproject.read_text()

        # Check that moviepy is NOT in dependencies
        assert "moviepy" not in content.lower(), (
            "moviepy must be removed from model/audio/pyproject.toml dependencies"
        )
