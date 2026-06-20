"""Unit tests for .claude/skills/gts-video/SKILL.md documentation."""

from pathlib import Path

import pytest


class TestGtsVideoSkillDocumentation:
    """Tests for gts-video skill file."""

    @pytest.fixture
    def skill_file(self) -> Path:
        return Path(".claude/skills/gts-video/SKILL.md")

    def test_skill_file_exists(self, skill_file: Path) -> None:
        """Verify gts-video skill file exists."""
        assert skill_file.exists(), f"Expected {skill_file} to exist"

    def test_skill_has_yaml_frontmatter(self, skill_file: Path) -> None:
        """Verify skill file has YAML frontmatter with required fields."""
        content = skill_file.read_text()
        assert content.startswith("---\n"), "Skill file must start with YAML frontmatter delimiter"

        lines = content.split("\n")
        frontmatter_end = None
        for i, line in enumerate(lines[1:], start=1):
            if line == "---":
                frontmatter_end = i
                break

        assert frontmatter_end is not None, (
            "Skill file must have closing YAML frontmatter delimiter"
        )

        frontmatter = "\n".join(lines[1:frontmatter_end])
        assert "name: gts-video" in frontmatter, "Skill frontmatter must include 'name: gts-video'"
        assert "description:" in frontmatter, "Skill frontmatter must include 'description:' field"

    def test_skill_covers_model_video_structure(self, skill_file: Path) -> None:
        """Verify skill documents model/video/ structure (not contexts/video/)."""
        content = skill_file.read_text()
        assert "model/video/" in content, "Skill must document model/video/ location"
        assert "contexts/video/" not in content, "Skill must NOT reference old contexts/video/ path"

    def test_skill_covers_video_api_patterns(self, skill_file: Path) -> None:
        """Verify skill documents video BC API (FastAPI endpoints)."""
        content = skill_file.read_text()
        assert any(
            keyword in content
            for keyword in ["api.py", "POST /render", "render endpoint", "FastAPI"]
        ), "Skill must document video API patterns"

    def test_skill_covers_remotion_components(self, skill_file: Path) -> None:
        """Verify skill documents Remotion composition patterns."""
        content = skill_file.read_text()
        assert any(
            keyword in content for keyword in ["Remotion", "compositions", "ShootoutVideo", "React"]
        ), "Skill must document Remotion components"

    def test_skill_covers_image_preparation(self, skill_file: Path) -> None:
        """Verify skill documents image preprocessing (Pillow)."""
        content = skill_file.read_text()
        assert any(
            keyword in content
            for keyword in ["image_prep", "Pillow", "image normalisation", "resize"]
        ), "Skill must document image preparation patterns"

    def test_skill_covers_props_serialisation(self, skill_file: Path) -> None:
        """Verify skill documents domain-to-Remotion props serialisation."""
        content = skill_file.read_text()
        assert any(
            keyword in content for keyword in ["props", "serialisation", "CompositionSpec", "JSON"]
        ), "Skill must document props serialisation"

    def test_skill_covers_video_service_docker(self, skill_file: Path) -> None:
        """Verify skill documents video service container."""
        content = skill_file.read_text()
        assert any(
            keyword in content
            for keyword in ["video service", "Docker", "container", "remotion render"]
        ), "Skill must document video service Docker integration"

    def test_skill_covers_dependency_rules(self, skill_file: Path) -> None:
        """Verify skill documents video layer dependency constraints."""
        content = skill_file.read_text()
        assert any(keyword in content for keyword in ["dependency", "gts", "import-linter"]), (
            "Skill must document video dependency rules (video depends on gts only)"
        )

    def test_skill_covers_testing_patterns(self, skill_file: Path) -> None:
        """Verify skill documents video test locations and patterns."""
        content = skill_file.read_text()
        assert any(
            keyword in content
            for keyword in ["tests/unit/backend/video", "tests/integration/backend/video", "pytest"]
        ), "Skill must document video testing patterns"

    def test_skill_covers_rendering_workflow(self, skill_file: Path) -> None:
        """Verify skill documents end-to-end rendering workflow."""
        content = skill_file.read_text()
        assert any(keyword in content for keyword in ["rendering", "workflow", "job", "status"]), (
            "Skill must document rendering workflow (job submission, status polling)"
        )

    def test_skill_covers_remotion_commands(self, skill_file: Path) -> None:
        """Verify skill documents Remotion CLI commands."""
        content = skill_file.read_text()
        assert any(
            keyword in content for keyword in ["remotion studio", "remotion render", "just"]
        ), "Skill must document Remotion commands"
