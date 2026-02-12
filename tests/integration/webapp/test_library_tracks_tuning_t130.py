"""Integration tests for Library DI Tracks tuning passthrough (T130).

The library tracks fragment endpoint at GET /api/v1/html/library/tracks
should render the track's tuning metadata when present. Currently the
endpoint hardcodes tuning to None instead of using the entity's tuning
field, causing tuning data to be lost in the library view.

These tests verify that tuning metadata is correctly passed through
from the database to the rendered HTML fragment.
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
async def track_with_tuning(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a DI track with tuning metadata set.

    Uses a tuning value that does NOT appear anywhere else in the track
    metadata (name, description, guitar, pickup) to ensure assertions
    are testing the tuning field specifically.
    """
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Clean Recording",
        file_path="/app/uploads/di-tracks/clean.wav",
        original_filename="clean.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        channels=1,
        guitar="Gibson Les Paul",
        pickup="Bridge Humbucker",
        tuning="Eb Standard",
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def authenticated_client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client against the real app."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksTuningPassthrough:
    """Tests that library tracks fragment renders tuning metadata.

    The library_tracks_fragment endpoint currently hardcodes tuning=None
    instead of passing through the entity's tuning field. These tests
    will fail until the endpoint is fixed to use t.tuning.
    """

    async def test_fragment_renders_tuning_when_present(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        track_with_tuning: DITrack,
    ) -> None:
        """Fragment should render tuning value 'Eb Standard' in the HTML output.

        Currently fails because library_tracks_fragment hardcodes tuning=None
        on line 496 of html.py instead of using t.tuning from the entity.
        The tuning value 'Eb Standard' does not appear in any other field
        (name, description, guitar, pickup) so this specifically tests
        the tuning passthrough.
        """
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        assert "Eb Standard" in response.text
