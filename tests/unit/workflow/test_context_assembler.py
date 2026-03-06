"""Tests for context_assembler — section extraction and area detection prompt."""

from workflow.context_assembler import (
    AREA_DESCRIPTIONS,
    _build_area_prompt,
    extract_sections,
)


class TestBuildAreaPrompt:
    """Test that the area detection prompt is well-formed."""

    def test_includes_all_areas(self):
        prompt = _build_area_prompt("test epic body")
        for area_id in AREA_DESCRIPTIONS:
            assert area_id in prompt

    def test_includes_epic_body(self):
        body = "Add comment editing to shootouts"
        prompt = _build_area_prompt(body)
        assert body in prompt


class TestExtractSections:
    """Test CONTEXT marker extraction."""

    def test_extracts_named_section(self):
        content = (
            "before\n"
            "<!-- CONTEXT:domain-model -->\n"
            "Domain model content here.\n"
            "<!-- /CONTEXT -->\n"
            "after"
        )
        result = extract_sections(content, ["domain-model"])
        assert "domain-model" in result
        assert "Domain model content here." in result["domain-model"]

    def test_ignores_unrequested_sections(self):
        content = (
            "<!-- CONTEXT:auth -->\nAuth content\n<!-- /CONTEXT -->\n"
            "<!-- CONTEXT:api-design -->\nAPI content\n<!-- /CONTEXT -->"
        )
        result = extract_sections(content, ["auth"])
        assert "auth" in result
        assert "api-design" not in result

    def test_missing_section_silently_omitted(self):
        content = "no markers here"
        result = extract_sections(content, ["nonexistent"])
        assert result == {}
