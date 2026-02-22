"""Tests for context_assembler — token budgeting and section trimming."""

from workflow.context_assembler import (
    CHARS_PER_TOKEN,
    _trim_to_budget,
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


class TestTrimToBudget:
    """Test section trimming to fit token budget."""

    def _make_content(self, tokens: int) -> str:
        """Create a string of approximately `tokens` estimated tokens."""
        return "x" * (tokens * CHARS_PER_TOKEN)

    def test_under_budget_no_trimming(self):
        wiki = {"GTS-Technical-Architecture :: domain-model": self._make_content(100)}
        codebase = {"STRUCTURE": self._make_content(100)}
        epic = self._make_content(100)

        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=1000)

        assert len(wiki) == 1
        assert len(codebase) == 1
        assert trimmed == []

    def test_trims_lowest_priority_wiki_first(self):
        # domain-model is high priority, infrastructure is low priority
        wiki = {
            "GTS-Technical-Architecture :: domain-model": self._make_content(5000),
            "GTS-Technical-Architecture :: infrastructure": self._make_content(5000),
        }
        codebase = {"STRUCTURE": self._make_content(100)}
        epic = self._make_content(100)

        # Budget only fits ~5200 tokens — must trim one wiki section
        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=5500)

        assert "GTS-Technical-Architecture :: infrastructure" not in wiki
        assert "GTS-Technical-Architecture :: domain-model" in wiki
        assert "GTS-Technical-Architecture :: infrastructure" in trimmed

    def test_full_wiki_files_trimmed_before_sections(self):
        # Full wiki files (no "::") have lowest priority
        wiki = {
            "GTS-Technical-Architecture :: architecture-layers": self._make_content(2000),
            "Frontend-Architecture": self._make_content(5000),
        }
        codebase = {"STRUCTURE": self._make_content(100)}
        epic = self._make_content(100)

        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=3000)

        assert "Frontend-Architecture" not in wiki
        assert "GTS-Technical-Architecture :: architecture-layers" in wiki
        assert "Frontend-Architecture" in trimmed

    def test_codebase_trimmed_after_wiki(self):
        # Even after trimming all wiki, if still over budget, trim codebase (but not STRUCTURE)
        wiki: dict[str, str] = {}  # Already empty
        codebase = {
            "STRUCTURE": self._make_content(2000),
            "SCHEMA": self._make_content(5000),
            "ENDPOINTS": self._make_content(5000),
        }
        epic = self._make_content(100)

        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=3000)

        assert "STRUCTURE" in codebase  # Never trimmed
        assert "SCHEMA" not in codebase or "ENDPOINTS" not in codebase
        assert any("codebase/" in t for t in trimmed)

    def test_structure_never_trimmed(self):
        codebase = {"STRUCTURE": self._make_content(10000)}
        wiki: dict[str, str] = {}
        epic = self._make_content(100)

        # Budget way under — but STRUCTURE still not trimmed
        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=100)

        assert "STRUCTURE" in codebase
        assert "codebase/STRUCTURE" not in trimmed

    def test_multiple_sections_trimmed_in_priority_order(self):
        wiki = {
            "GTS-Technical-Architecture :: architecture-layers": self._make_content(2000),
            "GTS-Technical-Architecture :: domain-model": self._make_content(2000),
            "GTS-Technical-Architecture :: testing": self._make_content(2000),
            "GTS-Technical-Architecture :: infrastructure": self._make_content(2000),
        }
        codebase = {"STRUCTURE": self._make_content(100)}
        epic = self._make_content(100)

        # Budget fits ~4200 — need to trim 2 of 4 wiki sections
        wiki, codebase, trimmed = _trim_to_budget(wiki, codebase, epic, budget_tokens=4500)

        # infrastructure and testing should be trimmed (lower priority)
        # architecture-layers and domain-model should remain (higher priority)
        assert "GTS-Technical-Architecture :: architecture-layers" in wiki
        assert "GTS-Technical-Architecture :: domain-model" in wiki
        assert len(trimmed) == 2


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
