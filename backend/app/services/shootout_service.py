"""Shootout service for managing shootout CRUD operations."""

import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shootout import Shootout, ToneSelection
from app.models.user import User
from app.schemas.shootout import (
    ShootoutCreate,
    ShootoutUpdate,
    ToneSelectionCreate,
)


class ShootoutService:
    """Service layer for Shootout CRUD operations."""

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session."""
        self.db = db

    async def create_shootout(
        self, user: User, shootout_in: ShootoutCreate
    ) -> Shootout:
        """Create a new shootout for the user.

        Args:
            user: The authenticated user creating the shootout.
            shootout_in: Shootout creation data.

        Returns:
            The created Shootout instance.
        """
        # Create the shootout
        shootout = Shootout(
            user_id=user.id,
            name=shootout_in.name,
            description=shootout_in.description,
            di_track_path=shootout_in.di_track_path,
            di_track_original_name=shootout_in.di_track_original_name,
            output_format=shootout_in.output_format,
            sample_rate=shootout_in.sample_rate,
            guitar=shootout_in.guitar,
            pickup=shootout_in.pickup,
            di_track_description=shootout_in.di_track_description,
        )
        self.db.add(shootout)
        await self.db.flush()

        # Create tone selections
        for tone_data in shootout_in.tone_selections:
            tone_selection = self._create_tone_selection(shootout.id, tone_data)
            self.db.add(tone_selection)

        await self.db.flush()
        await self.db.refresh(shootout)

        # Load relationships
        result = await self.db.execute(
            select(Shootout)
            .options(selectinload(Shootout.tone_selections))
            .where(Shootout.id == shootout.id)
        )
        return result.scalar_one()

    def _create_tone_selection(
        self, shootout_id: UUID, tone_data: ToneSelectionCreate
    ) -> ToneSelection:
        """Create a ToneSelection from schema data.

        Args:
            shootout_id: The parent shootout ID.
            tone_data: Tone selection creation data.

        Returns:
            The created ToneSelection instance (not yet persisted).
        """
        effects_json = None
        if tone_data.effects:
            effects_json = json.dumps([e.model_dump() for e in tone_data.effects])

        return ToneSelection(
            shootout_id=shootout_id,
            tone3000_tone_id=tone_data.tone3000_tone_id,
            tone3000_model_id=tone_data.tone3000_model_id,
            tone_title=tone_data.tone_title,
            model_name=tone_data.model_name,
            model_size=tone_data.model_size,
            gear_type=tone_data.gear_type,
            display_name=tone_data.display_name,
            description=tone_data.description,
            ir_path=tone_data.ir_path,
            highpass=tone_data.highpass,
            effects_json=effects_json,
            position=tone_data.position,
        )

    async def get_shootout(self, user: User, shootout_id: UUID) -> Shootout | None:
        """Get a shootout by ID, ensuring it belongs to the user.

        Args:
            user: The authenticated user.
            shootout_id: The shootout ID to retrieve.

        Returns:
            The Shootout if found and owned by user, None otherwise.
        """
        result = await self.db.execute(
            select(Shootout)
            .options(selectinload(Shootout.tone_selections))
            .where(Shootout.id == shootout_id, Shootout.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def get_shootout_by_id(self, shootout_id: UUID) -> Shootout | None:
        """Get a shootout by ID without user check (for public access).

        Args:
            shootout_id: The shootout ID to retrieve.

        Returns:
            The Shootout if found, None otherwise.
        """
        result = await self.db.execute(
            select(Shootout)
            .options(selectinload(Shootout.tone_selections))
            .where(Shootout.id == shootout_id)
        )
        return result.scalar_one_or_none()

    async def list_shootouts(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Shootout], int]:
        """List shootouts for a user.

        Args:
            user: The authenticated user.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (shootouts list, total count).
        """
        # Build base query
        query = select(Shootout).where(Shootout.user_id == user.id)
        count_query = (
            select(func.count())
            .select_from(Shootout)
            .where(Shootout.user_id == user.id)
        )

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = (
            query.options(selectinload(Shootout.tone_selections))
            .order_by(Shootout.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        shootouts = list(result.scalars().all())

        return shootouts, total

    async def list_public_shootouts(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Shootout], int]:
        """List public (processed) shootouts for browsing.

        Only returns shootouts that have been successfully processed.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (shootouts list, total count).
        """
        # Build base query for processed shootouts only
        query = select(Shootout).where(Shootout.is_processed.is_(True))
        count_query = (
            select(func.count())
            .select_from(Shootout)
            .where(Shootout.is_processed.is_(True))
        )

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = (
            query.options(selectinload(Shootout.tone_selections))
            .order_by(Shootout.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        shootouts = list(result.scalars().all())

        return shootouts, total

    async def update_shootout(
        self,
        user: User,
        shootout_id: UUID,
        shootout_update: ShootoutUpdate,
    ) -> Shootout | None:
        """Update a shootout.

        Args:
            user: The authenticated user.
            shootout_id: The shootout ID to update.
            shootout_update: The update data.

        Returns:
            The updated Shootout if found and owned by user, None otherwise.
        """
        shootout = await self.get_shootout(user, shootout_id)
        if not shootout:
            return None

        # Update only provided fields
        update_data = shootout_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(shootout, field, value)

        await self.db.flush()
        await self.db.refresh(shootout)

        # Reload with relationships
        result = await self.db.execute(
            select(Shootout)
            .options(selectinload(Shootout.tone_selections))
            .where(Shootout.id == shootout.id)
        )
        return result.scalar_one()

    async def delete_shootout(self, user: User, shootout_id: UUID) -> bool:
        """Delete a shootout.

        Args:
            user: The authenticated user.
            shootout_id: The shootout ID to delete.

        Returns:
            True if deleted, False if not found or not owned by user.
        """
        shootout = await self.get_shootout(user, shootout_id)
        if not shootout:
            return False

        await self.db.delete(shootout)
        await self.db.flush()
        return True
