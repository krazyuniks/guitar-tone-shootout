"""SQLAlchemy implementation of DITrackRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.domain.entities.di_track import DITrack as DITrackEntity
from core.domain.value_objects.audio_checksum import AudioChecksum
from sqlalchemy import func, select
from webapp.adapters.persistence.models.shootout import DITrack

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyDITrackRepository:
    """SQLAlchemy implementation of DITrackRepository protocol.

    Maps between domain DITrack entities and ORM DITrack models.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, track_id: UUID) -> DITrackEntity | None:
        """Get a DI track by its ID.

        Args:
            track_id: The track's UUID

        Returns:
            The DITrack entity if found, None otherwise
        """
        stmt = select(DITrack).where(DITrack.id == track_id)
        result = await self.session.execute(stmt)
        track = result.scalar_one_or_none()

        if track is None:
            return None

        return self._to_entity(track)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DITrackEntity]:
        """Get DI tracks for a user.

        Args:
            user_id: The owner's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of DITracks ordered by created_at desc
        """
        stmt = (
            select(DITrack)
            .where(DITrack.user_id == user_id)
            .order_by(DITrack.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        tracks = result.scalars().all()

        return [self._to_entity(track) for track in tracks]

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count DI tracks for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            Count of tracks
        """
        stmt = select(func.count()).select_from(DITrack).where(DITrack.user_id == user_id)
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count or 0

    async def save(self, track: DITrackEntity) -> None:
        """Save a DI track (create or update).

        Args:
            track: The track to save
        """
        # Check if track exists
        stmt = select(DITrack).where(DITrack.id == track.id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new track
            orm_track = DITrack(
                id=track.id,
                user_id=track.user_id,
                name=track.name,
                file_path=track.file_path,
                original_filename=track.original_filename,
                duration_seconds=track.duration_seconds,
                sample_rate=track.sample_rate,
                description=track.description,
                guitar=track.guitar,
                pickup=track.pickup,
                checksum=track.checksum.value if track.checksum else None,
                created_at=track.created_at,
                updated_at=track.updated_at,
            )
            self.session.add(orm_track)
        else:
            # Update existing track
            existing.name = track.name
            existing.file_path = track.file_path
            existing.original_filename = track.original_filename
            existing.duration_seconds = track.duration_seconds
            existing.sample_rate = track.sample_rate
            existing.description = track.description
            existing.guitar = track.guitar
            existing.pickup = track.pickup
            existing.checksum = track.checksum.value if track.checksum else None
            existing.updated_at = track.updated_at

        await self.session.flush()

    async def delete(self, track_id: UUID) -> None:
        """Delete a DI track by ID.

        Args:
            track_id: The track's UUID
        """
        stmt = select(DITrack).where(DITrack.id == track_id)
        result = await self.session.execute(stmt)
        track = result.scalar_one_or_none()

        if track is not None:
            await self.session.delete(track)
            await self.session.flush()

    def _to_entity(self, orm_track: DITrack) -> DITrackEntity:
        """Convert ORM DITrack to domain entity.

        Args:
            orm_track: ORM DITrack model

        Returns:
            Domain DITrack entity
        """
        return DITrackEntity(
            id=orm_track.id,
            user_id=orm_track.user_id,
            name=orm_track.name,
            file_path=orm_track.file_path,
            original_filename=orm_track.original_filename,
            duration_seconds=orm_track.duration_seconds,
            sample_rate=orm_track.sample_rate,
            description=orm_track.description,
            guitar=orm_track.guitar,
            pickup=orm_track.pickup,
            checksum=AudioChecksum(orm_track.checksum) if orm_track.checksum else None,
            waveform=None,  # Not stored in database
            created_at=orm_track.created_at,
            updated_at=orm_track.updated_at,
        )
