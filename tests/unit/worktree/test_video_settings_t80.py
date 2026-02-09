"""Unit tests for T80: Video service Settings configuration.

Tests that Settings class includes video port configuration.
"""

import pytest

from worktree.config import Settings


class TestVideoPortSettings:
    """Tests for video port in Settings."""

    def test_settings_has_base_port_video_attribute(self):
        """Settings should have base_port_video field."""
        settings = Settings()
        assert hasattr(settings, "base_port_video"), (
            "Settings missing base_port_video attribute"
        )

    def test_base_port_video_default_is_8002(self):
        """Default video port should be 8002 (matches docker-compose.yml)."""
        settings = Settings()
        assert settings.base_port_video == 8002

    def test_base_port_video_can_be_overridden(self):
        """base_port_video should be configurable via environment."""
        # Settings uses env_prefix = "GTS_WORKTREE_"
        # So GTS_WORKTREE_BASE_PORT_VIDEO should override the default
        import os

        old_value = os.environ.get("GTS_WORKTREE_BASE_PORT_VIDEO")
        try:
            os.environ["GTS_WORKTREE_BASE_PORT_VIDEO"] = "9002"
            settings = Settings()
            assert settings.base_port_video == 9002
        finally:
            if old_value is None:
                os.environ.pop("GTS_WORKTREE_BASE_PORT_VIDEO", None)
            else:
                os.environ["GTS_WORKTREE_BASE_PORT_VIDEO"] = old_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
