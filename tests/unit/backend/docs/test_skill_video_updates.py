"""Unit tests for video BC updates to existing skill files."""

from pathlib import Path

import pytest


class TestGtsArchitectureSkillVideoUpdates:
    """Tests for video BC integration in gts-architecture skill."""

    @pytest.fixture
    def skill_file(self) -> Path:
        return Path(".claude/skills/gts-architecture/SKILL.md")

    def test_skill_mentions_video_bc(self, skill_file: Path) -> None:
        """Verify gts-architecture skill mentions video BC."""
        content = skill_file.read_text()
        assert any(
            keyword in content.lower() for keyword in ["video", "remotion", "composition"]
        ), "gts-architecture skill must mention video BC"

    def test_skill_documents_video_dependency_rule(self, skill_file: Path) -> None:
        """Verify gts-architecture documents video layer dependency constraints."""
        content = skill_file.read_text()
        # Should mention that video can depend on core + audio
        assert any(keyword in content for keyword in ["video", "dependency", "audio", "core"]), (
            "gts-architecture must document video dependency rule (video → core + audio)"
        )


class TestGtsTestingSkillVideoUpdates:
    """Tests for video test patterns in gts-testing skill."""

    @pytest.fixture
    def skill_file(self) -> Path:
        return Path(".claude/skills/gts-testing/SKILL.md")

    def test_skill_includes_video_test_locations(self, skill_file: Path) -> None:
        """Verify gts-testing documents video test file locations."""
        content = skill_file.read_text()
        assert any(location in content for location in ["video/"]), (
            "gts-testing must document video test locations"
        )

    def test_skill_includes_video_test_patterns(self, skill_file: Path) -> None:
        """Verify gts-testing documents patterns for testing video components."""
        content = skill_file.read_text()
        assert any(
            keyword in content.lower() for keyword in ["video", "remotion", "composition", "render"]
        ), "gts-testing must include video-specific test patterns"

    def test_skill_documents_video_fixtures(self, skill_file: Path) -> None:
        """Verify gts-testing documents video test fixtures or patterns."""
        content = skill_file.read_text()
        # Should mention how to test video components (fixtures, mocking, etc.)
        assert any(keyword in content for keyword in ["video test", "composition test", "props"]), (
            "gts-testing must document video test fixtures/patterns"
        )
