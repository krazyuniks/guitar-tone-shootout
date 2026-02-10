"""E2E tests for DI Track Audio Player UI.

Tests the HTML5 audio player integration on public browse and library pages,
verifying that audio players are present, correctly wired to the stream endpoint,
and that all interactive elements have data-testid attributes.
"""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.asyncio
@pytest.mark.e2e
class TestDITrackAudioPlayerPublicBrowse:
    """Test audio player on public DI tracks browse page."""

    async def test_public_browse_page_has_audio_players(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Public browse page shows inline audio player per track."""
        # Navigate to public DI tracks page
        await guest_page.goto(f"{frontend_url}/di-tracks")

        # Wait for HTMX to load results
        await guest_page.wait_for_selector('[data-testid="di-tracks-results"]', timeout=5000)

        # Check if there are any tracks displayed
        track_items = guest_page.locator('[data-testid="track-item"]')
        track_count = await track_items.count()

        # If tracks exist, verify audio players
        if track_count > 0:
            # Each track should have an audio player
            first_track = track_items.first
            audio_player = first_track.locator('audio[data-testid="track-audio-player"]')
            await expect(audio_player).to_be_visible()

    async def test_audio_player_src_points_to_stream_endpoint(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Audio player src points to /api/v1/di-tracks/{id}/stream."""
        await guest_page.goto(f"{frontend_url}/di-tracks")
        await guest_page.wait_for_selector('[data-testid="di-tracks-results"]', timeout=5000)

        # Get first track's audio player
        audio_player = guest_page.locator('audio[data-testid="track-audio-player"]').first

        if await audio_player.count() > 0:
            # Verify src attribute contains stream endpoint
            src = await audio_player.get_attribute("src")
            assert src is not None
            assert "/api/v1/di-tracks/" in src
            assert "/stream" in src

    async def test_audio_player_has_controls(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """Audio player has controls attribute enabled."""
        await guest_page.goto(f"{frontend_url}/di-tracks")
        await guest_page.wait_for_selector('[data-testid="di-tracks-results"]', timeout=5000)

        audio_player = guest_page.locator('audio[data-testid="track-audio-player"]').first

        if await audio_player.count() > 0:
            # Verify controls attribute is present
            controls = await audio_player.get_attribute("controls")
            assert controls is not None


@pytest.mark.asyncio
@pytest.mark.e2e
class TestDITrackAudioPlayerLibrary:
    """Test audio player on library DI tracks page."""

    async def test_library_page_has_audio_players(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library page shows inline audio player per track."""
        # Navigate to library DI tracks page (requires auth, uses authenticated page fixture)
        await page.goto(f"{frontend_url}/library/di-tracks")

        # Wait for HTMX to load tracks list
        await page.wait_for_selector('[data-testid="di-tracks-library"]', timeout=5000)

        # Check if there are any tracks displayed
        track_items = page.locator('[data-testid="track-item"]')
        track_count = await track_items.count()

        # If tracks exist, verify audio players
        if track_count > 0:
            # Each track should have an audio player
            first_track = track_items.first
            audio_player = first_track.locator('audio[data-testid="track-audio-player"]')
            await expect(audio_player).to_be_visible()

    async def test_library_audio_player_src_correct(
        self, page: Page, frontend_url: str
    ) -> None:
        """Library page audio player src points to correct stream endpoint."""
        await page.goto(f"{frontend_url}/library/di-tracks")
        await page.wait_for_selector('[data-testid="di-tracks-library"]', timeout=5000)

        # Get first track's audio player
        audio_player = page.locator('audio[data-testid="track-audio-player"]').first

        if await audio_player.count() > 0:
            # Verify src attribute
            src = await audio_player.get_attribute("src")
            assert src is not None
            assert "/api/v1/di-tracks/" in src
            assert "/stream" in src


@pytest.mark.asyncio
@pytest.mark.e2e
class TestDITrackUploadForm:
    """Test upload form on library page."""

    async def test_upload_form_has_required_testids(
        self, page: Page, frontend_url: str
    ) -> None:
        """Upload form has data-testid attributes on all interactive elements."""
        await page.goto(f"{frontend_url}/library/di-tracks")
        await page.wait_for_selector('[data-testid="di-tracks-library"]', timeout=5000)

        # Click upload button to open modal
        upload_btn = page.locator('[data-testid="upload-track-btn"]')
        await expect(upload_btn).to_be_visible()
        await upload_btn.click()

        # Verify modal is visible
        modal = page.locator('#upload-modal')
        await expect(modal).to_be_visible()

        # Verify form has testid
        upload_form = page.locator('[data-testid="upload-track-form"]')
        await expect(upload_form).to_be_visible()

        # Verify input fields have testids
        await expect(page.locator('[data-testid="upload-title-input"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-file-input"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-guitar-input"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-pickups-input"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-tuning-input"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-description-textarea"]')).to_be_visible()

        # Verify buttons have testids
        await expect(page.locator('[data-testid="upload-cancel-btn"]')).to_be_visible()
        await expect(page.locator('[data-testid="upload-submit-btn"]')).to_be_visible()

    async def test_upload_form_uses_htmx(
        self, page: Page, frontend_url: str
    ) -> None:
        """Upload form uses HTMX for submission without page reload."""
        await page.goto(f"{frontend_url}/library/di-tracks")
        await page.wait_for_selector('[data-testid="di-tracks-library"]', timeout=5000)

        # Open modal
        await page.locator('[data-testid="upload-track-btn"]').click()

        # Check form has HTMX attributes
        form = page.locator('[data-testid="upload-track-form"]')

        # Verify hx-post attribute
        hx_post = await form.get_attribute("hx-post")
        assert hx_post is not None
        assert "/api/v1/di-tracks/upload" in hx_post

        # Verify hx-encoding for multipart
        hx_encoding = await form.get_attribute("hx-encoding")
        assert hx_encoding == "multipart/form-data"

        # Verify hx-target
        hx_target = await form.get_attribute("hx-target")
        assert hx_target is not None


@pytest.mark.asyncio
@pytest.mark.e2e
class TestTrackItemInteractiveElements:
    """Test that track item components have proper testids."""

    async def test_track_item_has_all_testids(
        self, guest_page: Page, frontend_url: str
    ) -> None:
        """All interactive elements in track items have data-testid attributes."""
        await guest_page.goto(f"{frontend_url}/di-tracks")
        await guest_page.wait_for_selector('[data-testid="di-tracks-results"]', timeout=5000)

        track_items = guest_page.locator('[data-testid="track-item"]')

        if await track_items.count() > 0:
            first_track = track_items.first

            # Verify track expand button has testid
            expand_btn = first_track.locator('[data-testid="track-expand-btn"]')
            await expect(expand_btn).to_be_visible()

            # Verify audio player has testid (this will fail initially)
            audio_player = first_track.locator('[data-testid="track-audio-player"]')
            await expect(audio_player).to_be_attached()
