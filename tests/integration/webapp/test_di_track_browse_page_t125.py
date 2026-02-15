"""Integration tests for DI track browse page and HTMX results fragment (T125).

Tests verify:
1. GET /di-tracks renders browse page with correct data-testid attributes
2. GET /api/v1/html/di-tracks/results returns paginated results with track metadata
3. Search/filter by name works via HTMX partial reload
4. Pagination controls render when tracks exceed page limit
5. Each track shows: name, waveform, duration, guitar, pickup, tuning
6. Tuning field is passed through from database (not hardcoded to None)
7. Empty state renders when no tracks exist
8. Browse page includes a search input with data-testid
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app


@pytest.fixture
async def browse_user(db_session: AsyncSession) -> User:
    """Create a user who owns DI tracks for browse tests."""
    user = User(
        id=uuid4(),
        username="browseowner",
        email="browseowner@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def browse_tracks(db_session: AsyncSession, browse_user: User) -> list[DITrack]:
    """Create sample DI tracks with varied metadata for browse testing."""
    tracks = []
    track_data = [
        {
            "name": "Clean Strat DI",
            "duration_seconds": 30.0,
            "guitar": "Fender Stratocaster",
            "pickup": "Neck Single Coil",
            "tuning": "E Standard",
            "description": "Clean Stratocaster recording",
        },
        {
            "name": "Drop D Riff",
            "duration_seconds": 45.5,
            "guitar": "Gibson Les Paul",
            "pickup": "Bridge Humbucker",
            "tuning": "Drop D",
            "description": "Heavy riff in Drop D",
        },
        {
            "name": "Open Tuning Slide",
            "duration_seconds": 60.0,
            "guitar": None,
            "pickup": None,
            "tuning": "Open G",
            "description": None,
        },
    ]
    for i, data in enumerate(track_data):
        track = DITrack(
            id=uuid4(),
            user_id=browse_user.id,
            name=data["name"],
            file_path=f"/app/uploads/di-tracks/{browse_user.id}/browse{i}.wav",
            original_filename=f"browse{i}.wav",
            duration_seconds=data["duration_seconds"],
            sample_rate=44100,
            description=data["description"],
            guitar=data["guitar"],
            pickup=data["pickup"],
            tuning=data["tuning"],
        )
        db_session.add(track)
        tracks.append(track)
    await db_session.flush()
    return tracks


@pytest.fixture
async def pagination_tracks(db_session: AsyncSession, browse_user: User) -> list[DITrack]:
    """Create enough tracks to trigger pagination (>50 default limit)."""
    tracks = []
    for i in range(55):
        track = DITrack(
            id=uuid4(),
            user_id=browse_user.id,
            name=f"Page Track {i + 1:03d}",
            file_path=f"/app/uploads/di-tracks/{browse_user.id}/page{i}.wav",
            original_filename=f"page{i}.wav",
            duration_seconds=10.0 + i,
            sample_rate=48000,
        )
        db_session.add(track)
        tracks.append(track)
    await db_session.flush()
    return tracks


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackBrowsePage:
    """Test GET /di-tracks public browse page."""

    async def test_returns_200(self, db_session: AsyncSession) -> None:
        """GET /di-tracks returns 200 with HTML content."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_has_page_testid(self, db_session: AsyncSession) -> None:
        """Browse page has data-testid='di-tracks-browse-page'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        assert 'data-testid="di-tracks-browse-page"' in response.text

    async def test_has_search_input(self, db_session: AsyncSession) -> None:
        """Browse page includes a search input with data-testid for testing.

        The search input should be visible in the initial page load (not
        only in the HTMX-loaded fragment), so users can search immediately.
        """
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        assert 'data-testid="di-tracks-search-input"' in response.text

    async def test_has_htmx_trigger(self, db_session: AsyncSession) -> None:
        """Browse page triggers HTMX to load results from the fragment endpoint."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        html = response.text
        assert "hx-get" in html
        assert "/api/v1/html/di-tracks/results" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsFragmentMetadata:
    """Test GET /api/v1/html/di-tracks/results returns track metadata."""

    async def test_returns_200(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results fragment returns 200."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_has_results_testid(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results fragment has data-testid='di-tracks-results'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert 'data-testid="di-tracks-results"' in response.text

    async def test_shows_track_names(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results display each track's name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "Clean Strat DI" in html
        assert "Drop D Riff" in html
        assert "Open Tuning Slide" in html

    async def test_shows_total_count(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results display total track count."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert "3 tracks found" in response.text

    async def test_shows_duration(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results display formatted duration for each track."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        # 30s → "0:30", 45.5s → "0:45", 60s → "1:00"
        assert "0:30" in html
        assert "0:45" in html
        assert "1:00" in html

    async def test_shows_guitar_metadata(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results display guitar name when present."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "Fender Stratocaster" in html
        assert "Gibson Les Paul" in html

    async def test_shows_pickup_metadata(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results display pickup info when present."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "Neck Single Coil" in html
        assert "Bridge Humbucker" in html

    async def test_shows_tuning_metadata(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Results must pass through tuning from database, not hardcode None.

        Currently html.py has 'tuning': None hardcoded. It should be
        'tuning': t.tuning to pass the actual value from the database.
        """
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "E Standard" in html
        assert "Drop D" in html
        assert "Open G" in html

    async def test_track_items_have_testid(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Each track card has data-testid='track-item'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert response.text.count('data-testid="track-item"') >= 3

    async def test_track_items_have_audio_player(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Each track has an audio player element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert response.text.count('data-testid="track-audio-player"') >= 3

    async def test_track_items_have_waveform(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Each track has a waveform visualisation element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert response.text.count('data-testid="track-waveform"') >= 3


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsSearch:
    """Test search/filter by name on the results fragment."""

    async def test_search_filters_by_name(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Search parameter filters tracks by name (ILIKE)."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results", params={"search": "Strat"}
            )

        html = response.text
        assert "Clean Strat DI" in html
        assert "Drop D Riff" not in html

    async def test_search_shows_filtered_count(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Search result shows correct filtered count."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results", params={"search": "Strat"}
            )

        assert "1 track found" in response.text

    async def test_search_no_results_shows_empty(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """Search with no matches shows empty state with filter hint."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results",
                params={"search": "NonExistentTrack999"},
            )

        html = response.text
        assert "No DI Tracks Found" in html
        assert "adjust" in html.lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsPagination:
    """Test pagination on the results fragment."""

    async def test_next_shown_when_more_tracks(
        self, db_session: AsyncSession, pagination_tracks: list[DITrack]
    ) -> None:
        """Next link appears when tracks exceed page limit."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert "Next" in response.text

    async def test_prev_shown_with_offset(
        self, db_session: AsyncSession, pagination_tracks: list[DITrack]
    ) -> None:
        """Previous link appears when offset > 0."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results", params={"offset": 50})

        assert "Previous" in response.text

    async def test_no_controls_when_all_fit(
        self, db_session: AsyncSession, browse_tracks: list[DITrack]
    ) -> None:
        """No pagination controls when all tracks fit on one page."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "Next" not in html
        assert "Previous" not in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsEmptyState:
    """Test empty state rendering."""

    async def test_empty_state_no_tracks(self, db_session: AsyncSession) -> None:
        """Results fragment shows empty state when no tracks exist."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "No DI Tracks Found" in html
        assert "No public DI tracks are available yet" in html
