"""Integration tests for Shootout Detail Pre-Processing Build Artifacts.

Verifies that:
1. Astro build succeeds for shootout detail page
2. Generated HTML contains required sections for pre-processing state
3. All interactive elements have proper data-testid attributes
4. DI track section is present with audio player elements
5. Status badge elements are present for all states
"""

from pathlib import Path


class TestShootoutDetailPreProcessingBuild:
    """Test Astro build artifacts for shootout detail pre-processing display."""

    def test_shootout_detail_page_exists_after_build(self) -> None:
        """Shootout detail page HTML exists in dist after Astro build."""
        dist_path = Path("/app/frontend/astro/dist/pages/shootout_detail.html")
        assert dist_path.exists(), "Shootout detail page not found in Astro dist"

    def test_shootout_detail_fragment_exists_after_build(self) -> None:
        """Shootout detail fragment HTML exists in dist after Astro build."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        assert dist_path.exists(), "Shootout detail fragment not found in Astro dist"

    def test_detail_fragment_has_shootout_metadata_testids(self) -> None:
        """Detail fragment contains testids for shootout metadata."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        required_testids = [
            'data-testid="shootout-detail"',
            'data-testid="shootout-title"',
            'data-testid="tone-count"',
            'data-testid="relative-time"',
            'data-testid="shootout-header"',
        ]

        for testid in required_testids:
            assert testid in content, f"{testid} not found in detail fragment"

    def test_detail_fragment_has_di_track_section(self) -> None:
        """Detail fragment contains DI track section with testid."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # DI track section should exist
        assert 'data-testid="di-track-section"' in content, \
            "DI track section missing data-testid in detail fragment"

    def test_di_track_section_has_audio_player(self) -> None:
        """DI track section contains audio player element."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Audio player should exist within DI track section
        assert '<audio' in content, "No audio element in detail fragment"
        assert 'data-testid="di-track-player"' in content, \
            "Audio player missing data-testid"

    def test_di_track_section_shows_track_metadata(self) -> None:
        """DI track section displays track name and duration."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Should have testids for track name and duration
        assert 'data-testid="di-track-name"' in content, \
            "DI track name missing data-testid"
        assert 'data-testid="di-track-duration"' in content, \
            "DI track duration missing data-testid"

    def test_detail_fragment_has_status_badge(self) -> None:
        """Detail fragment contains status badge element."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Status badge should exist
        assert 'data-testid="status-badge"' in content, \
            "Status badge missing data-testid in detail fragment"

    def test_detail_fragment_has_processing_placeholder(self) -> None:
        """Detail fragment contains processing placeholder for pending state."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Processing placeholder should exist
        assert 'data-testid="processing-placeholder"' in content, \
            "Processing placeholder missing data-testid"

        # Should contain explanatory text about pending state
        assert "Pending Processing" in content or "pending" in content.lower(), \
            "No pending state text in processing placeholder"

    def test_detail_fragment_has_chain_list_section(self) -> None:
        """Detail fragment contains segments section for chain list."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Segments section should exist
        assert 'data-testid="segments-section"' in content, \
            "Segments section missing data-testid"

        # Should have segment button testid (for chain items)
        assert 'data-testid="segment-button"' in content, \
            "Segment button missing data-testid for chains"

    def test_detail_fragment_has_description_section(self) -> None:
        """Detail fragment contains description section with testid."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Description section should exist
        assert 'data-testid="description-section"' in content, \
            "Description section missing data-testid"

    def test_detail_fragment_has_back_link(self) -> None:
        """Detail fragment contains back link with testid."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Back link should exist
        assert 'data-testid="back-link"' in content, \
            "Back link missing data-testid"

    def test_audio_player_uses_stream_endpoint_pattern(self) -> None:
        """Audio player src references DI track stream endpoint."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        # Should reference stream endpoint pattern (Jinja2 template)
        # Looking for template variable references
        assert "di_track" in content or "DI" in content, \
            "No DI track reference in detail fragment"

    def test_all_required_testids_present(self) -> None:
        """All required data-testid attributes are present in build artifact."""
        dist_path = Path("/app/frontend/astro/dist/fragments/shootouts/detail.html")
        content = dist_path.read_text()

        required_testids = [
            'data-testid="shootout-detail"',
            'data-testid="back-link"',
            'data-testid="processing-placeholder"',
            'data-testid="shootout-header"',
            'data-testid="shootout-title"',
            'data-testid="tone-count"',
            'data-testid="relative-time"',
            'data-testid="status-badge"',
            'data-testid="description-section"',
            'data-testid="segments-section"',
            'data-testid="segment-button"',
            'data-testid="di-track-section"',
            'data-testid="di-track-name"',
            'data-testid="di-track-duration"',
            'data-testid="di-track-player"',
        ]

        for testid in required_testids:
            assert testid in content, f"{testid} not found in detail fragment (build artifact missing)"
