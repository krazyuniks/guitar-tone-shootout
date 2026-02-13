"""Unit tests for audio package cleanup.

Verifies that:
- libs/audio/src/audio/video/ stub is removed
- moviepy dependency is removed from libs/audio/pyproject.toml
"""

from pathlib import Path

import pytest


class TestAudioCleanup:
    """Test audio package cleanup (video stub and moviepy removed)."""

    @pytest.fixture
    def audio_root(self) -> Path:
        """Path to libs/audio/ directory."""
        return Path("libs/audio")

    @pytest.fixture
    def audio_src(self, audio_root: Path) -> Path:
        """Path to libs/audio/src/audio/ directory."""
        return audio_root / "src" / "audio"

    def test_video_stub_removed(self, audio_src: Path) -> None:
        """libs/audio/src/audio/video/ stub directory removed."""
        video_stub = audio_src / "video"
        assert not video_stub.exists(), "libs/audio/src/audio/video/ stub must be removed"

    def test_moviepy_dependency_removed(self, audio_root: Path) -> None:
        """moviepy dependency removed from libs/audio/pyproject.toml."""
        pyproject = audio_root / "pyproject.toml"
        content = pyproject.read_text()

        # Check that moviepy is NOT in dependencies
        assert "moviepy" not in content.lower(), (
            "moviepy must be removed from libs/audio/pyproject.toml dependencies"
        )
