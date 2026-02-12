"""Integration tests for Library DI Tracks page (T130).

Tests the library DI tracks page focusing on tuning field propagation
through the repository and HTML fragment layers.

Bugs found:
1. DITrackRepository._to_entity omits tuning field (always None)
2. DITrackRepository.save() omits tuning field (never persisted)
3. library_tracks_fragment hardcodes "tuning": None instead of t.tuning
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def track_with_tuning(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a DI track with tuning information set."""
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Drop D Riff",
        file_path="/app/uploads/di-tracks/drop_d.wav",
        original_filename="drop_d.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        channels=1,
        guitar="Gibson Les Paul",
        pickup="Bridge Humbucker",
        tuning="Drop D",
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


@pytest.mark.asyncio
@pytest.mark.integration
class TestDITrackRepositoryTuningField:
    """Tests that tuning field is preserved through repository layer."""

    async def test_get_by_id_preserves_tuning(
        self, db_session: AsyncSession, test_user: User, track_with_tuning: DITrack
    ) -> None:
        """Repository.get_by_id returns entity with tuning field populated."""
        repo = SQLAlchemyDITrackRepository(db_session)
        entity = await repo.get_by_id(track_with_tuning.id)

        assert entity is not None
        assert entity.tuning == "Drop D"

    async def test_get_by_user_id_preserves_tuning(
        self, db_session: AsyncSession, test_user: User, track_with_tuning: DITrack
    ) -> None:
        """Repository.get_by_user_id returns entities with tuning field populated."""
        repo = SQLAlchemyDITrackRepository(db_session)
        entities = await repo.get_by_user_id(test_user.id)

        assert len(entities) >= 1
        tuned_track = next(e for e in entities if e.name == "Drop D Riff")
        assert tuned_track.tuning == "Drop D"

    async def test_save_persists_tuning_field(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Repository.save() persists the tuning field to the database."""
        from core.domain.entities.di_track import DITrack as DITrackEntity

        entity = DITrackEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="DADGAD Test",
            file_path="/app/uploads/di-tracks/dadgad.wav",
            original_filename="dadgad.wav",
            duration_seconds=25.0,
            sample_rate=44100,
            tuning="DADGAD",
        )

        repo = SQLAlchemyDITrackRepository(db_session)
        await repo.save(entity)
        await db_session.commit()

        # Re-read from database to verify persistence
        from sqlalchemy import select

        db_session.expire_all()
        stmt = select(DITrack).where(DITrack.id == entity.id)
        result = await db_session.execute(stmt)
        orm_track = result.scalar_one()

        assert orm_track.tuning == "DADGAD"


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksFragmentTuning:
    """Tests that tuning field is rendered in library tracks HTMX fragment."""

    async def test_fragment_includes_tuning_in_metadata(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Library tracks fragment includes tuning value in rendered HTML."""
        # Create track with tuning that won't appear in name or other fields
        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name="Clean Test",
            file_path="/app/uploads/di-tracks/clean.wav",
            original_filename="clean.wav",
            duration_seconds=30.0,
            sample_rate=44100,
            channels=1,
            tuning="DADGAD",
        )
        db_session.add(track)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/tracks")

        assert response.status_code == 200
        html = response.text
        # Tuning should appear in the rendered fragment metadata
        assert "DADGAD" in html
