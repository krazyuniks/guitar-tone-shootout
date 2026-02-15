"""Integration tests for tuning data in Library DI Tracks fragment (T130).

Tests that tuning metadata is correctly passed through from database
to the rendered HTML fragment for the library tracks list.

Bug: The library_tracks_fragment handler hardcodes tuning to None
instead of using the actual tuning value from the track entity.
Additionally, the repository _to_entity method omits tuning from
the domain entity mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def authenticated_client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client against the real app."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def track_with_tuning(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a DI track with tuning metadata set."""
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Drop D Riff",
        file_path="/app/uploads/di-tracks/drop_d.wav",
        original_filename="drop_d.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        channels=1,
        guitar="ESP Eclipse",
        pickup="Bridge Humbucker",
        tuning="Drop D",
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksFragmentTuning:
    """Tests verifying tuning data flows through to the rendered fragment."""

    async def test_fragment_renders_tuning_metadata(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        track_with_tuning: DITrack,
    ) -> None:
        """Fragment renders the tuning value when a track has tuning set.

        Bug: library_tracks_fragment hardcodes tuning to None instead of
        passing t.tuning from the domain entity. This test verifies
        the tuning value ("Drop D") appears in the rendered HTML.
        """
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text
        assert "Drop D" in html

    async def test_fragment_renders_tuning_for_multiple_tracks(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Fragment renders different tuning values for each track.

        Creates two tracks with different tunings and verifies both appear.
        """
        track1 = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Standard Track",
            file_path="/app/uploads/di-tracks/standard.wav",
            original_filename="standard.wav",
            duration_seconds=20.0,
            sample_rate=44100,
            channels=1,
            tuning="E Standard",
        )
        track2 = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Open G Track",
            file_path="/app/uploads/di-tracks/openg.wav",
            original_filename="openg.wav",
            duration_seconds=25.0,
            sample_rate=44100,
            channels=1,
            tuning="Open G",
        )
        db_session.add_all([track1, track2])
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text
        assert "E Standard" in html
        assert "Open G" in html
