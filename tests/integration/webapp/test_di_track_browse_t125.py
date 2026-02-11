"""Integration tests for DI track browse page and results fragment (T125).

Tests verify:
1. GET /di-tracks renders the public browse page with correct structure
2. GET /api/v1/html/di-tracks/results returns paginated track results
3. Search/filter by name works via query parameter
4. Pagination controls render when needed
5. Each track shows: name, duration, guitar, pickup, tuning
6. Tuning field is passed through (not hardcoded to None)
7. Empty state renders when no tracks exist
8. Page has data-testid attributes for testing
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app


@pytest.fixture
async def tracks_user(db_session: AsyncSession) -> User:
    """Create a user who owns DI tracks for browse tests."""
    user = User(
        id=uuid4(),
        username="trackowner",
        email="trackowner@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def sample_tracks(db_session: AsyncSession, tracks_user: User) -> list[DITrack]:
    """Create sample DI tracks for browse page tests."""
    tracks = []
    for i in range(3):
        track = DITrack(
            id=uuid4(),
            user_id=tracks_user.id,
            name=f"Test Track {i + 1}",
            file_path=f"/app/uploads/di-tracks/{tracks_user.id}/track{i}.wav",
            original_filename=f"track{i}.wav",
            duration_seconds=30.0 + i * 10,
            sample_rate=44100,
            description=f"Description for track {i + 1}",
            guitar="Fender Stratocaster" if i == 0 else None,
            pickup="Bridge Humbucker" if i == 1 else None,
            tuning="E Standard" if i == 0 else ("Drop D" if i == 1 else None),
        )
        db_session.add(track)
        tracks.append(track)
    await db_session.flush()
    return tracks


@pytest.fixture
async def many_tracks(db_session: AsyncSession, tracks_user: User) -> list[DITrack]:
    """Create enough tracks to require pagination (more than default limit)."""
    tracks = []
    for i in range(55):
        track = DITrack(
            id=uuid4(),
            user_id=tracks_user.id,
            name=f"Paginated Track {i + 1:03d}",
            file_path=f"/app/uploads/di-tracks/{tracks_user.id}/ptrack{i}.wav",
            original_filename=f"ptrack{i}.wav",
            duration_seconds=10.0 + i,
            sample_rate=48000,
        )
        db_session.add(track)
        tracks.append(track)
    await db_session.flush()
    return tracks


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackBrowsePageRoute:
    """Test the /di-tracks public browse page route."""

    async def test_browse_page_returns_200(self, db_session: AsyncSession) -> None:
        """GET /di-tracks should return 200 with HTML content."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_browse_page_has_testid(self, db_session: AsyncSession) -> None:
        """Browse page must have data-testid='di-tracks-browse-page'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        assert 'data-testid="di-tracks-browse-page"' in response.text

    async def test_browse_page_has_search_input(self, db_session: AsyncSession) -> None:
        """Browse page must include a search input for filtering tracks by name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        html = response.text
        assert 'data-testid="di-tracks-search-input"' in html

    async def test_browse_page_has_htmx_load_trigger(self, db_session: AsyncSession) -> None:
        """Browse page must trigger HTMX load to fetch results."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/di-tracks")

        html = response.text
        assert "hx-get" in html
        assert "/api/v1/html/di-tracks/results" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsFragment:
    """Test GET /api/v1/html/di-tracks/results HTMX fragment."""

    async def test_results_returns_200_with_tracks(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results fragment returns 200 with track data."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_results_has_testid(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results fragment must have data-testid='di-tracks-results'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert 'data-testid="di-tracks-results"' in response.text

    async def test_results_show_track_names(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results fragment must display track names."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "Test Track 1" in html
        assert "Test Track 2" in html
        assert "Test Track 3" in html

    async def test_results_show_track_count(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results fragment must display total track count."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert "3 tracks found" in response.text

    async def test_results_show_guitar_metadata(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results must show guitar metadata when present."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert "Fender Stratocaster" in response.text

    async def test_results_show_pickup_metadata(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results must show pickup metadata when present."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        assert "Bridge Humbucker" in response.text

    async def test_results_show_tuning_metadata(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results must pass through tuning field (not hardcode None).

        Currently html.py:446 has "tuning": None hardcoded. It should
        be "tuning": t.tuning to pass the actual value.
        """
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "E Standard" in html

    async def test_results_show_duration(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Results must show formatted duration for each track."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        # 30s track should show as "0:30"
        assert "0:30" in html

    async def test_results_include_track_items_with_testid(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Each track in results must have data-testid='track-item'."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert html.count('data-testid="track-item"') >= 3

    async def test_results_include_audio_player(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Each track must have an audio player element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert html.count('data-testid="track-audio-player"') >= 3

    async def test_results_include_waveform(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Each track must have a waveform visualisation element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert html.count('data-testid="track-waveform"') >= 3


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsSearch:
    """Test search/filter functionality on the results fragment."""

    async def test_search_filters_by_name(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Search parameter must filter tracks by name (ILIKE match)."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results", params={"search": "Track 1"}
            )

        html = response.text
        assert "Test Track 1" in html
        assert "Test Track 2" not in html

    async def test_search_returns_count(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Search result must show correct filtered count."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results", params={"search": "Track 1"}
            )

        assert "1 track found" in response.text

    async def test_search_no_results_shows_empty_state(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
    ) -> None:
        """Search with no matches must show empty state with filter hint."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/di-tracks/results",
                params={"search": "NonexistentTrackName"},
            )

        html = response.text
        assert "No DI Tracks Found" in html
        assert "adjust" in html.lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackResultsPagination:
    """Test pagination on the results fragment."""

    async def test_pagination_controls_shown_when_needed(
        self, db_session: AsyncSession, many_tracks: list[DITrack]
    ) -> None:
        """Pagination controls must appear when more tracks than page limit."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        # Should have a "Next" link since 55 tracks > default 50
        assert "Next" in html

    async def test_pagination_offset_works(
        self, db_session: AsyncSession, many_tracks: list[DITrack]
    ) -> None:
        """Offset parameter must skip tracks."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results", params={"offset": 50})

        html = response.text
        # Should show "Previous" link when offset > 0
        assert "Previous" in html

    async def test_pagination_no_controls_when_all_fit(
        self, db_session: AsyncSession, sample_tracks: list[DITrack]
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

    async def test_empty_state_when_no_tracks(self, db_session: AsyncSession) -> None:
        """Results fragment must show empty state when no tracks exist."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/di-tracks/results")

        html = response.text
        assert "No DI Tracks Found" in html
        assert "No public DI tracks are available yet" in html
