"""Unit tests verifying shootout templates are built from Astro sources."""

from pathlib import Path


class TestShootoutTemplatesBuilt:
    """Verify that shootout page templates are built and available."""

    def test_library_shootouts_page_template_exists(self) -> None:
        """Test that pages/library/shootouts.html template is built."""
        template_path = Path("frontend/astro/dist/pages/library/shootouts.html")
        assert template_path.exists(), (
            f"Template {template_path} not found. "
            "Run 'just build-astro' to build frontend templates."
        )

    def test_shootout_detail_page_template_exists(self) -> None:
        """Test that pages/shootout_detail.html template is built."""
        template_path = Path("frontend/astro/dist/pages/shootout_detail.html")
        assert template_path.exists(), (
            f"Template {template_path} not found. "
            "Run 'just build-astro' to build frontend templates."
        )

    def test_library_shootouts_page_source_exists(self) -> None:
        """Test that pages/library/shootouts.html.ts source file exists."""
        source_path = Path("frontend/astro/src/pages/pages/library/shootouts.html.ts")
        assert (
            source_path.exists()
        ), f"Source template {source_path} not found. Create the Astro page template source file."

    def test_shootout_detail_page_source_exists(self) -> None:
        """Test that pages/shootout_detail.html.ts source file exists."""
        source_path = Path("frontend/astro/src/pages/pages/shootout_detail.html.ts")
        assert (
            source_path.exists()
        ), f"Source template {source_path} not found. Create the Astro page template source file."
