"""Tests for context_assembler — token estimation and section extraction."""

from workflow.context_assembler import (
    estimate_context_tokens,
    extract_sections,
    scan_keywords,
)


class TestEstimateContextTokens:
    """Test token estimation."""

    def test_basic_estimate(self):
        text = "a" * 400
        assert estimate_context_tokens(text) == 100

    def test_empty_string(self):
        assert estimate_context_tokens("") == 0


class TestScanKeywords:
    """Test keyword scanning (existing functionality, for coverage)."""

    def test_detects_signal_chain_area(self):
        areas = scan_keywords("This epic adds a new amp model to the signal chain")
        assert "signal_chain" in areas

    def test_detects_frontend_area(self):
        areas = scan_keywords("Add a new page template for the gear library UI")
        assert "frontend_layers" in areas

    def test_no_areas_from_generic_text(self):
        areas = scan_keywords("Bump version number to 2.0")
        assert len(areas) == 0


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
