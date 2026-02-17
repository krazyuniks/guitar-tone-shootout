"""Integration tests for Library DI Tracks page and fragment (T130).

Tests the library DI tracks page rendering, fragment endpoint
for user's tracks list, and track metadata display including
the tuning field which is currently missing from the fragment handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
async def sample_track(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a sample DI track with full metadata."""
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Clean Strat Recording",
        file_path="/app/storage/uploads/di_tracks/clean_strat.wav",
        original_filename="clean_strat.wav",
        duration_seconds=45.5,
        sample_rate=48000,
        channels=1,
        guitar="Fender Stratocaster",
        pickup="Neck Single Coil",
        tuning="E Standard",
        description="Clean recording for comparison",
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create a second user for isolation tests."""
    user = User(
        id=uuid4(),
        username="other_user",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksFragmentMetadata:
    """Tests verifying track metadata flows through to the rendered fragment."""

    async def test_fragment_includes_tuning_from_entity(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        sample_track: DITrack,
    ) -> None:
        """Fragment renders tuning value from the track entity.

        Bug: The library_tracks_fragment handler hardcodes tuning to None
        (line ~497 of html.py) instead of passing the actual tuning from
        the domain entity. The tuning should appear in the rendered HTML
        when a track has a tuning value set.
        """
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text

        # Track name should appear
        assert "Clean Strat Recording" in html

        # Tuning value should appear in the rendered output
        # This fails because the handler hardcodes "tuning": None
        assert "E Standard" in html

    async def test_fragment_renders_upload_date(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        sample_track: DITrack,
    ) -> None:
        """Fragment renders the upload date as relative time."""
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text

        # relative_time for a just-created track should show "just now"
        assert "just now" in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackRepositoryTuning:
    """Tests that the DI track repository preserves tuning in entity mapping."""

    async def test_to_entity_includes_tuning(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Repository _to_entity maps tuning from ORM to domain entity.

        Bug: SQLAlchemyDITrackRepository._to_entity does not pass the
        tuning field when constructing DITrackEntity, so tuning is always
        None in the domain entity even when the ORM model has tuning data.
        """
        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Tuning Test",
            file_path="/app/storage/uploads/di_tracks/tuning.wav",
            original_filename="tuning.wav",
            duration_seconds=10.0,
            sample_rate=44100,
            channels=1,
            tuning="Drop C",
        )
        db_session.add(track)
        await db_session.commit()

        repo = SQLAlchemyDITrackRepository(db_session)
        entity = await repo.get_by_id(track.id)

        assert entity is not None
        assert entity.tuning == "Drop C"

    async def test_get_by_user_id_preserves_tuning(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Repository get_by_user_id preserves tuning in returned entities."""
        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="DADGAD Track",
            file_path="/app/storage/uploads/di_tracks/dadgad.wav",
            original_filename="dadgad.wav",
            duration_seconds=20.0,
            sample_rate=44100,
            channels=1,
            tuning="DADGAD",
        )
        db_session.add(track)
        await db_session.commit()

        repo = SQLAlchemyDITrackRepository(db_session)
        entities = await repo.get_by_user_id(test_user.id)

        assert len(entities) >= 1
        matching = [e for e in entities if e.name == "DADGAD Track"]
        assert len(matching) == 1
        assert matching[0].tuning == "DADGAD"


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksFragmentIsolation:
    """Tests that the library tracks fragment only shows the current user's tracks."""

    async def test_fragment_excludes_other_users_tracks(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Fragment only shows tracks owned by the authenticated user.

        Another user's tracks should never appear in the library fragment.
        """
        # Create track for the authenticated user
        my_track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="My Private Riff",
            file_path="/app/storage/uploads/di_tracks/my_riff.wav",
            original_filename="my_riff.wav",
            duration_seconds=15.0,
            sample_rate=44100,
            channels=1,
        )
        # Create track for another user
        other_track = DITrack(
            id=uuid4(),
            user_id=other_user.id,
            name="Other Users Secret Song",
            file_path="/app/storage/uploads/di_tracks/other.wav",
            original_filename="other.wav",
            duration_seconds=30.0,
            sample_rate=44100,
            channels=1,
        )
        db_session.add_all([my_track, other_track])
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text

        assert "My Private Riff" in html
        assert "Other Users Secret Song" not in html

    async def test_fragment_empty_state_when_no_tracks(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Fragment renders empty state when user has no tracks."""
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        html = response.text

        assert "No DI tracks yet" in html
        assert 'data-empty="true"' in html


@pytest.mark.asyncio
@pytest.mark.integration
class TestDeleteDITrackFromLibrary:
    """Tests for deleting DI tracks and verifying they disappear from the fragment."""

    async def test_delete_track_removes_from_fragment(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        sample_track: DITrack,
    ) -> None:
        """After deleting a track, it no longer appears in the library fragment."""
        # Verify track appears before deletion
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        assert "Clean Strat Recording" in response.text

        # Delete the track
        delete_response = await authenticated_client.delete(f"/api/v1/di-tracks/{sample_track.id}")
        assert delete_response.status_code == 204

        # Verify track no longer appears in fragment
        response = await authenticated_client.get("/api/v1/html/library/tracks")
        assert response.status_code == 200
        assert "Clean Strat Recording" not in response.text

    async def test_delete_nonexistent_track_returns_404(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Deleting a non-existent track returns 404."""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/di-tracks/{fake_id}")
        assert response.status_code == 404

    async def test_delete_other_users_track_returns_404(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Deleting another user's track returns 404 (no existence leak)."""
        other_track = DITrack(
            id=uuid4(),
            user_id=other_user.id,
            name="Not My Track",
            file_path="/app/storage/uploads/di_tracks/notmine.wav",
            original_filename="notmine.wav",
            duration_seconds=10.0,
            sample_rate=44100,
            channels=1,
        )
        db_session.add(other_track)
        await db_session.commit()

        response = await authenticated_client.delete(f"/api/v1/di-tracks/{other_track.id}")
        assert response.status_code == 404

        # Verify the track still exists in the database
        result = await db_session.execute(select(DITrack).where(DITrack.id == other_track.id))
        assert result.scalar_one_or_none() is not None
