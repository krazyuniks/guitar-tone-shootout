"""Unit tests for gear page template structure."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
class TestGearBrowseTemplate:
    """Test gear browse template exists and has required structure."""

    def test_gear_browse_template_exists(self) -> None:
        """Verify gear browse template file exists."""
        # Check source file
        template_src = Path("frontend/astro/src/pages/pages/gear_browse.html.ts")
        assert template_src.exists(), f"Template source not found: {template_src}"

        # Check built output
        template_dist = Path("frontend/astro/dist/pages/gear_browse.html")
        assert template_dist.exists(), f"Built template not found: {template_dist}"

    def test_gear_browse_template_extends_base_layout(self) -> None:
        """Verify gear browse template extends base layout."""
        template_path = Path("frontend/astro/dist/pages/gear_browse.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify it extends base layout
        assert '{% extends "layouts/base.html" %}' in content

    def test_gear_browse_template_has_required_blocks(self) -> None:
        """Verify gear browse template has required Jinja2 blocks."""
        template_path = Path("frontend/astro/dist/pages/gear_browse.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify required blocks
        assert "{% block title %}" in content
        assert "{% block content %}" in content

    def test_gear_browse_template_has_testid_attributes(self) -> None:
        """Verify gear browse template has data-testid attributes for testing."""
        template_path = Path("frontend/astro/dist/pages/gear_browse.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify required test IDs
        assert 'data-testid="gear-browse-page"' in content
        assert 'data-testid="gear-browse-heading"' in content
        assert 'data-testid="gear-list-container"' in content
        assert 'data-testid="gear-type-filter"' in content
        assert 'data-testid="manufacturer-filter"' in content
        assert 'data-testid="gear-search-input"' in content

    def test_gear_browse_template_has_htmx_attributes(self) -> None:
        """Verify gear browse template uses HTMX for dynamic updates."""
        template_path = Path("frontend/astro/dist/pages/gear_browse.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify HTMX attributes are present
        assert "hx-get" in content or "hx-post" in content
        assert "hx-target" in content or "hx-swap" in content


@pytest.mark.unit
class TestGearDetailTemplate:
    """Test gear detail template exists and has required structure."""

    def test_gear_detail_template_exists(self) -> None:
        """Verify gear detail template file exists."""
        # Check source file
        template_src = Path("frontend/astro/src/pages/pages/gear_detail.html.ts")
        assert template_src.exists(), f"Template source not found: {template_src}"

        # Check built output
        template_dist = Path("frontend/astro/dist/pages/gear_detail.html")
        assert template_dist.exists(), f"Built template not found: {template_dist}"

    def test_gear_detail_template_extends_base_layout(self) -> None:
        """Verify gear detail template extends base layout."""
        template_path = Path("frontend/astro/dist/pages/gear_detail.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify it extends base layout
        assert '{% extends "layouts/base.html" %}' in content

    def test_gear_detail_template_has_required_blocks(self) -> None:
        """Verify gear detail template has required Jinja2 blocks."""
        template_path = Path("frontend/astro/dist/pages/gear_detail.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify required blocks
        assert "{% block title %}" in content
        assert "{% block content %}" in content

    def test_gear_detail_template_has_testid_attributes(self) -> None:
        """Verify gear detail template has data-testid attributes for testing."""
        template_path = Path("frontend/astro/dist/pages/gear_detail.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify required test IDs
        assert 'data-testid="gear-detail-page"' in content
        assert 'data-testid="gear-detail-name"' in content
        assert 'data-testid="gear-detail-type"' in content
        assert 'data-testid="gear-detail-manufacturer"' in content
        assert 'data-testid="gear-detail-description"' in content
        assert 'data-testid="back-to-browse-link"' in content

    def test_gear_detail_template_uses_jinja2_variables(self) -> None:
        """Verify gear detail template uses Jinja2 variables for dynamic content."""
        template_path = Path("frontend/astro/dist/pages/gear_detail.html")
        assert template_path.exists()

        content = template_path.read_text()

        # Verify Jinja2 variable usage (gear object passed from FastAPI)
        assert "{{ gear" in content or "{{gear" in content


@pytest.mark.unit
class TestGearFragmentTemplates:
    """Test HTMX fragment templates exist."""

    def test_gear_fragments_directory_exists(self) -> None:
        """Verify gear fragments directory exists."""
        fragments_src = Path("frontend/astro/src/pages/fragments/gear")
        assert fragments_src.exists(), f"Fragments source directory not found: {fragments_src}"

        fragments_dist = Path("frontend/astro/dist/fragments/gear")
        assert fragments_dist.exists(), f"Fragments dist directory not found: {fragments_dist}"

    def test_gear_list_fragment_exists(self) -> None:
        """Verify gear list fragment template exists."""
        # Common patterns for HTMX fragments
        possible_names = [
            "list.html",
            "gear_list.html",
            "gear-list.html",
        ]

        fragments_dir = Path("frontend/astro/dist/fragments/gear")
        assert fragments_dir.exists()

        # Check if at least one variant exists
        found = False
        for name in possible_names:
            if (fragments_dir / name).exists():
                found = True
                break

        assert found, f"No gear list fragment found in {fragments_dir}"

    def test_gear_card_fragment_exists(self) -> None:
        """Verify gear card fragment template exists."""
        # Common patterns for card fragments
        possible_names = [
            "card.html",
            "gear_card.html",
            "gear-card.html",
        ]

        fragments_dir = Path("frontend/astro/dist/fragments/gear")
        assert fragments_dir.exists()

        # Check if at least one variant exists
        found = False
        for name in possible_names:
            if (fragments_dir / name).exists():
                found = True
                break

        assert found, f"No gear card fragment found in {fragments_dir}"
