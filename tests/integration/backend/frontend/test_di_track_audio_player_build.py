"""Integration tests for DI Track Audio Player UI build artifacts.

Verifies that:
1. Astro build succeeds with new DI track templates
2. Generated HTML contains audio player elements
3. Generated HTML has proper data-testid attributes for E2E tests
"""

from pathlib import Path


class TestDITrackAudioPlayerBuild:
    """Test Astro build artifacts for DI track audio player."""

    def test_public_di_tracks_page_exists_after_build(self) -> None:
        """Public DI tracks page HTML exists in dist after Astro build."""
        dist_path = Path("/app/frontend/astro/dist/di-tracks/index.html")
        assert dist_path.exists(), "Public DI tracks page not found in Astro dist"

    def test_library_di_tracks_page_exists_after_build(self) -> None:
        """Library DI tracks page HTML exists in dist after Astro build."""
        dist_path = Path("/app/frontend/astro/dist/library/di-tracks/index.html")
        assert dist_path.exists(), "Library DI tracks page not found in Astro dist"

    def test_public_di_tracks_page_contains_audio_element(self) -> None:
        """Public DI tracks page HTML contains audio player element."""
        dist_path = Path("/app/frontend/astro/dist/di-tracks/index.html")
        content = dist_path.read_text()

        # Should contain audio element
        assert "<audio" in content, "No audio element in public DI tracks page"

    def test_library_di_tracks_page_contains_audio_element(self) -> None:
        """Library DI tracks page HTML contains audio player element."""
        dist_path = Path("/app/frontend/astro/dist/library/di-tracks/index.html")
        content = dist_path.read_text()

        # Should contain audio element
        assert "<audio" in content, "No audio element in library DI tracks page"

    def test_audio_elements_have_testid_attribute(self) -> None:
        """Audio elements have data-testid for E2E testing."""
        public_path = Path("/app/frontend/astro/dist/di-tracks/index.html")
        public_content = public_path.read_text()

        # Should have data-testid on audio elements
        assert (
            'data-testid="track-audio-player"' in public_content
        ), "Audio player missing data-testid in public page"

    def test_library_page_contains_upload_form(self) -> None:
        """Library page contains upload form with proper structure."""
        dist_path = Path("/app/frontend/astro/dist/library/di-tracks/index.html")
        content = dist_path.read_text()

        # Should contain form element
        assert "<form" in content, "No form element in library page"

        # Should have upload button to trigger modal
        assert (
            'data-testid="upload-track-btn"' in content
        ), "Upload button missing data-testid in library page"

    def test_upload_form_has_htmx_attributes(self) -> None:
        """Upload form uses HTMX for submission."""
        dist_path = Path("/app/frontend/astro/dist/library/di-tracks/index.html")
        content = dist_path.read_text()

        # Should have hx-post attribute
        assert "hx-post" in content, "No hx-post attribute in library page form"

        # Should post to upload endpoint
        assert "/api/v1/di-tracks/upload" in content, "Upload form not posting to correct endpoint"

        # Should have hx-encoding for multipart
        assert (
            'hx-encoding="multipart/form-data"' in content
        ), "Upload form missing hx-encoding for file upload"

    def test_upload_form_fields_have_testids(self) -> None:
        """Upload form fields have data-testid attributes."""
        dist_path = Path("/app/frontend/astro/dist/library/di-tracks/index.html")
        content = dist_path.read_text()

        required_testids = [
            'data-testid="upload-track-form"',
            'data-testid="upload-title-input"',
            'data-testid="upload-file-input"',
            'data-testid="upload-guitar-input"',
            'data-testid="upload-pickups-input"',
            'data-testid="upload-tuning-input"',
            'data-testid="upload-description-textarea"',
            'data-testid="upload-submit-btn"',
            'data-testid="upload-cancel-btn"',
        ]

        for testid in required_testids:
            assert testid in content, f"{testid} not found in library page"

    def test_audio_player_src_uses_stream_endpoint(self) -> None:
        """Audio player src attribute references stream endpoint."""
        public_path = Path("/app/frontend/astro/dist/di-tracks/index.html")
        public_content = public_path.read_text()

        # Should reference stream endpoint pattern
        assert (
            "/api/v1/di-tracks/" in public_content
        ), "Audio player src not referencing DI tracks API"
        assert "/stream" in public_content, "Audio player src not referencing stream endpoint"

    def test_track_items_have_testid(self) -> None:
        """Track items have data-testid for identification."""
        public_path = Path("/app/frontend/astro/dist/di-tracks/index.html")
        public_content = public_path.read_text()

        # Track items should be identifiable
        assert (
            'data-testid="track-item"' in public_content
        ), "Track items missing data-testid in public page"
