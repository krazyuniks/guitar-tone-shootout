"""Integration tests for shootout creation wizard Step 2: DI Track Selection (T140).

Tests the /shootout/create/ditracks endpoint and DI track
selection modal behaviour for the shootout creation wizard.

Acceptance criteria tested:
- Step 2 endpoint returns user's DI tracks with name, duration, guitar, waveform
- Search/filter by name
- Single selection data (radio-style track objects)
- Duration formatted for display
- Only authenticated users can access
- Only user's own tracks returned
- data-testid attributes on interactive elements
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.pages.shootouts import router

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with html router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another user for isolation tests."""
    user = User(username="otheruser", email="other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_tracks(db_session: AsyncSession, test_user: User) -> list[DITrack]:
    """Create DI tracks for the test user."""
    tracks = [
        DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Clean Strat Recording",
            file_path="/audio/clean_strat.wav",
            original_filename="clean_strat.wav",
            duration_seconds=45.5,
            sample_rate=48000,
            guitar="Fender Stratocaster",
            pickup="neck",
            tuning="E Standard",
            description="Clean strat recording for testing",
        ),
        DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Les Paul Crunch",
            file_path="/audio/les_paul_crunch.wav",
            original_filename="les_paul_crunch.wav",
            duration_seconds=120.0,
            sample_rate=44100,
            guitar="Gibson Les Paul",
            pickup="bridge",
            tuning="Drop D",
            description="Les Paul bridge pickup crunch tone",
        ),
        DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Tele Fingerpicking",
            file_path="/audio/tele_finger.wav",
            original_filename="tele_finger.wav",
            duration_seconds=90.3,
            sample_rate=96000,
            guitar="Fender Telecaster",
            pickup="both",
            tuning="E Standard",
            description=None,
        ),
    ]
    for t in tracks:
        db_session.add(t)
    await db_session.flush()
    return tracks


@pytest.fixture
async def other_user_track(db_session: AsyncSession, other_user: User) -> DITrack:
    """Create a DI track for another user."""
    track = DITrack(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Track",
        file_path="/audio/other.wav",
        original_filename="other.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        guitar="ESP Eclipse",
    )
    db_session.add(track)
    await db_session.flush()
    return track


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    from webapp.auth.dependencies import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def unauthenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutWizardStep2DITrackList:
    """Test GET /shootout/create/ditracks returns user's DI tracks."""

    async def test_returns_user_tracks(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Endpoint returns all of the authenticated user's DI tracks."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # All three user tracks should appear
        assert "Clean Strat Recording" in html
        assert "Les Paul Crunch" in html
        assert "Tele Fingerpicking" in html

    async def test_track_shows_duration(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Each track displays duration in formatted form (mm:ss)."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # 45.5 seconds = 0:45, 120.0 seconds = 2:00, 90.3 seconds = 1:30
        assert "0:45" in html
        assert "2:00" in html
        assert "1:30" in html

    async def test_track_shows_guitar(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Each track displays the guitar name."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        assert "Fender Stratocaster" in html
        assert "Gibson Les Paul" in html
        assert "Fender Telecaster" in html

    async def test_track_shows_waveform_data(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Each track includes waveform visualisation data or placeholder.

        The acceptance criteria require 'waveform' display for each track.
        The response must include waveform-related markup.
        """
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # There should be waveform-related content in the response
        assert "waveform" in html.lower() or 'data-testid="ditrack-waveform"' in html

    async def test_does_not_return_other_users_tracks(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
        other_user_track: DITrack,
    ) -> None:
        """Endpoint only returns tracks owned by the authenticated user."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        assert "Other User Track" not in html

    async def test_track_has_data_testid_attribute(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Each track option has data-testid='ditrack-option' for Playwright testing."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # Each track should have a data-testid attribute
        assert html.count('data-testid="ditrack-option"') == len(user_tracks)

    async def test_empty_state_when_no_tracks(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Shows empty state when user has no DI tracks."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # Should show empty state messaging
        assert "No DI tracks" in html or "Upload DI Track" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutWizardStep2Search:
    """Test search/filter functionality for DI track selection."""

    async def test_search_filters_tracks_by_name(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Search parameter filters tracks by name (case-insensitive)."""
        response = await authenticated_client.get("/shootout/create/ditracks?search=strat")

        assert response.status_code == 200
        html = response.text

        # Should include the Strat track
        assert "Clean Strat Recording" in html
        # Should NOT include non-matching tracks
        assert "Les Paul Crunch" not in html
        assert "Tele Fingerpicking" not in html

    async def test_search_is_case_insensitive(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Search is case-insensitive."""
        response = await authenticated_client.get("/shootout/create/ditracks?search=LES PAUL")

        assert response.status_code == 200
        html = response.text

        # Should match "Les Paul Crunch" case-insensitively
        assert "Les Paul Crunch" in html
        # Should NOT include non-matching tracks
        assert "Clean Strat Recording" not in html
        assert "Tele Fingerpicking" not in html

    async def test_search_returns_empty_for_no_matches(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Search returns empty/no results for non-matching query."""
        response = await authenticated_client.get("/shootout/create/ditracks?search=nonexistent")

        assert response.status_code == 200
        html = response.text

        # None of the tracks should appear
        assert "Clean Strat Recording" not in html
        assert "Les Paul Crunch" not in html
        assert "Tele Fingerpicking" not in html

    async def test_empty_search_returns_all_tracks(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Empty search parameter returns all tracks."""
        response = await authenticated_client.get("/shootout/create/ditracks?search=")

        assert response.status_code == 200
        html = response.text

        assert "Clean Strat Recording" in html
        assert "Les Paul Crunch" in html
        assert "Tele Fingerpicking" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutWizardStep2Auth:
    """Test authentication requirements for step 2."""

    async def test_unauthenticated_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get("/shootout/create/ditracks")

        # Should be 401 or 403 for unauthenticated access
        assert response.status_code in [401, 403]


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutWizardStep2TrackData:
    """Test that track response data includes all required fields."""

    async def test_track_includes_duration_formatted(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Track data includes pre-formatted duration string for display.

        The acceptance criteria require showing duration. The endpoint should
        provide a formatted duration (mm:ss) alongside raw seconds.
        """
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # 45.5s track should show as "0:45"
        assert "0:45" in html
        # 120.0s track should show as "2:00"
        assert "2:00" in html

    async def test_track_includes_sample_rate(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Track data includes sample rate for display."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # Sample rates should be displayed (48kHz, 44.1kHz, 96kHz)
        assert "48" in html  # 48 kHz
        assert "44.1" in html or "44100" in html  # 44.1 kHz
        assert "96" in html  # 96 kHz

    async def test_track_data_includes_track_id_for_selection(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        user_tracks: list[DITrack],
    ) -> None:
        """Each track includes its ID for radio-style selection."""
        response = await authenticated_client.get("/shootout/create/ditracks")

        assert response.status_code == 200
        html = response.text

        # Each track ID should be present in the HTML
        for track in user_tracks:
            assert str(track.id) in html
