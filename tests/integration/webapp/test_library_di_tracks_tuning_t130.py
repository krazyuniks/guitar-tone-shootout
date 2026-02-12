"""Integration tests for tuning rendering in Library DI Tracks fragment (T130).

The library_tracks_fragment endpoint currently hardcodes tuning to None
instead of passing the actual track tuning value. These tests verify that
the tuning metadata is correctly rendered in the library tracks fragment.
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

    Uses a unique tuning string that won't appear in other fields.
    """
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="My Test Recording",
        file_path="/app/uploads/di-tracks/recording.wav",
        original_filename="recording.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        channels=1,
        guitar="PRS Custom 24",
        pickup="Bridge Humbucker",
        tuning="DADGAD",
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
class TestLibraryTracksFragmentTuning:
    """Verify that track tuning metadata is rendered in the library tracks fragment.

    The library_tracks_fragment endpoint must pass the actual tuning value
    to the template rather than hardcoding it to None.
    """

    async def test_fragment_renders_tuning_value(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        track_with_tuning: DITrack,
    ) -> None:
        """Library tracks fragment includes the track's tuning in the rendered HTML.

        The tuning 'DADGAD' is a distinctive string that won't appear in any
        other field (name, guitar, pickup), so its presence confirms that
        the tuning metadata is being passed through to the template.
        """
        response = await authenticated_client.get("/api/v1/html/library/tracks")

        assert response.status_code == 200
        html = response.text
        assert "DADGAD" in html
