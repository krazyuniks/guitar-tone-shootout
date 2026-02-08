"""SQLAlchemy implementation of GearRepository protocol."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import joinedload

from core.domain.entities.gear import Gear as GearEntity
from core.domain.entities.gear import GearModel as GearModelVO
from core.domain.entities.gear import GearSource as GearSourceVO
from webapp.adapters.persistence.models.gear import (
    Gear,
    GearModel,
    GearSource,
    GearTag,
    gear_tags_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from core.domain.value_objects.signal_chain_enums import GearType


def _slugify(text: str, manufacturer: str | None = None) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: The text to slugify
        manufacturer: Optional manufacturer name to prepend

    Returns:
        A lowercase, hyphenated slug
    """
    # Check if manufacturer is already in the name
    if manufacturer:
        # Case-insensitive check if name starts with manufacturer
        if text.lower().startswith(manufacturer.lower()):
            # Manufacturer already in name, don't duplicate
            combined = text
        else:
            # Prepend manufacturer
            combined = f"{manufacturer} {text}"
    else:
        combined = text

    # Convert to lowercase
    slug = combined.lower()
    # Normalize unicode characters (ö -> o, etc.)
    import unicodedata
    slug = unicodedata.normalize('NFKD', slug)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9-]+', '-', slug)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


class SQLAlchemyGearRepository:
    """SQLAlchemy implementation of GearRepository protocol.

    Maps between domain Gear entities and ORM Gear models, handling
    models, tags, and source relationships.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, gear_id: UUID) -> GearEntity | None:
        """Get gear by its internal ID.

        Args:
            gear_id: The gear's UUID

        Returns:
            The Gear entity if found, None otherwise
        """
        stmt = (
            select(Gear)
            .where(Gear.id == gear_id)
            .options(
                joinedload(Gear.models),
                joinedload(Gear.tags),
                joinedload(Gear.source),
                joinedload(Gear.make),
            )
        )
        result = await self.session.execute(stmt)
        gear = result.unique().scalar_one_or_none()
        return self._to_entity(gear) if gear else None

    async def get_by_slug(self, slug: str) -> GearEntity | None:
        """Get gear by its URL slug.

        Slug lookup is case-insensitive.

        Args:
            slug: The gear's URL slug

        Returns:
            The Gear entity if found, None otherwise
        """
        # Normalize slug to lowercase for case-insensitive lookup
        normalized_slug = slug.lower()
        stmt = (
            select(Gear)
            .where(func.lower(Gear.slug) == normalized_slug)
            .options(
                joinedload(Gear.models),
                joinedload(Gear.tags),
                joinedload(Gear.source),
                joinedload(Gear.make),
            )
        )
        result = await self.session.execute(stmt)
        gear = result.unique().scalar_one_or_none()
        return self._to_entity(gear) if gear else None

    async def get_by_source(
        self,
        source_name: str,
        source_record_id: str,
    ) -> GearEntity | None:
        """Get gear by its source identifier.

        Args:
            source_name: Name of the source (e.g., 't3k')
            source_record_id: ID in the source system

        Returns:
            The Gear entity if found, None otherwise
        """
        stmt = (
            select(Gear)
            .join(GearSource, Gear.source_id == GearSource.id)
            .where(
                GearSource.source_name == source_name,
                GearSource.source_record_id == source_record_id,
            )
            .options(
                joinedload(Gear.models),
                joinedload(Gear.tags),
                joinedload(Gear.source),
                joinedload(Gear.make),
            )
        )
        result = await self.session.execute(stmt)
        gear = result.unique().scalar_one_or_none()
        return self._to_entity(gear) if gear else None

    async def search(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GearEntity]:
        """Search for gear with filters.

        Args:
            query: Optional text search on name/description
            gear_type: Optional filter by gear type
            manufacturer: Optional filter by manufacturer
            tags: Optional filter by tags (AND logic)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching Gear ordered by name
        """
        stmt = select(Gear).options(
            joinedload(Gear.models),
            joinedload(Gear.tags),
            joinedload(Gear.source),
            joinedload(Gear.make),
        )

        # Apply filters
        conditions = []

        if query:
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    Gear.name.ilike(search_pattern),
                    Gear.description.ilike(search_pattern),
                )
            )

        if gear_type:
            conditions.append(Gear.gear_type == gear_type)

        if manufacturer:
            conditions.append(Gear.manufacturer == manufacturer)

        if tags:
            # AND logic for tags - gear must have all specified tags
            # Subquery approach: count how many of the requested tags each gear has
            tag_count = (
                select(gear_tags_table.c.gear_id)
                .join(GearTag, gear_tags_table.c.tag_id == GearTag.id)
                .where(GearTag.name.in_(tags))
                .group_by(gear_tags_table.c.gear_id)
                .having(func.count(gear_tags_table.c.tag_id) == len(tags))
            )
            conditions.append(Gear.id.in_(tag_count))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Order by name and apply pagination
        stmt = stmt.order_by(Gear.name).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        gear_items = result.unique().scalars().all()

        return [self._to_entity(gear) for gear in gear_items]

    async def count(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """Count gear matching filters.

        Args:
            query: Optional text search
            gear_type: Optional filter by gear type
            manufacturer: Optional filter by manufacturer
            tags: Optional filter by tags

        Returns:
            Count of matching gear
        """
        stmt = select(func.count(Gear.id))

        # Apply filters
        conditions = []

        if query:
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    Gear.name.ilike(search_pattern),
                    Gear.description.ilike(search_pattern),
                )
            )

        if gear_type:
            conditions.append(Gear.gear_type == gear_type)

        if manufacturer:
            conditions.append(Gear.manufacturer == manufacturer)

        if tags:
            # AND logic for tags - same subquery approach as search
            tag_count = (
                select(gear_tags_table.c.gear_id)
                .join(GearTag, gear_tags_table.c.tag_id == GearTag.id)
                .where(GearTag.name.in_(tags))
                .group_by(gear_tags_table.c.gear_id)
                .having(func.count(gear_tags_table.c.tag_id) == len(tags))
            )
            conditions.append(Gear.id.in_(tag_count))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def save(self, gear: GearEntity) -> None:
        """Save gear (create or update).

        Args:
            gear: The gear entity to save
        """
        # Check if gear exists - load with relationships for update
        stmt = (
            select(Gear)
            .where(Gear.id == gear.id)
            .options(
                joinedload(Gear.models),
                joinedload(Gear.tags),
                joinedload(Gear.source),
                joinedload(Gear.make),
            )
        )
        result = await self.session.execute(stmt)
        existing = result.unique().scalar_one_or_none()

        if existing:
            # Update existing gear
            existing.name = gear.name
            # Generate slug if not provided
            existing.slug = gear.slug if gear.slug else _slugify(gear.name, gear.manufacturer)
            existing.gear_type = gear.gear_type
            existing.description = gear.description
            existing.manufacturer = gear.manufacturer
            existing.thumbnail_url = gear.thumbnail_url
            existing.is_public = gear.is_public
            existing.updated_at = gear.updated_at

            # Update source if present
            if gear.source:
                if existing.source:
                    existing.source.source_name = gear.source.source_name
                    existing.source.source_record_id = gear.source.source_record_id
                    existing.source.source_updated_at = gear.source.source_updated_at
                else:
                    new_source = GearSource(
                        source_name=gear.source.source_name,
                        source_record_id=gear.source.source_record_id,
                        source_updated_at=gear.source.source_updated_at,
                    )
                    self.session.add(new_source)
                    await self.session.flush()
                    existing.source_id = new_source.id

            # Update tags
            await self._update_tags(existing, gear.tags)

            # Update models
            await self._update_models(existing, gear.models)
        else:
            # Create new gear
            # Generate slug if not provided
            slug = gear.slug if gear.slug else _slugify(gear.name, gear.manufacturer)
            new_gear = Gear(
                id=gear.id,
                name=gear.name,
                slug=slug,
                gear_type=gear.gear_type,
                description=gear.description,
                manufacturer=gear.manufacturer,
                thumbnail_url=gear.thumbnail_url,
                is_public=gear.is_public,
                created_at=gear.created_at,
                updated_at=gear.updated_at,
            )
            self.session.add(new_gear)
            await self.session.flush()

            # Add source if present
            if gear.source:
                new_source = GearSource(
                    source_name=gear.source.source_name,
                    source_record_id=gear.source.source_record_id,
                    source_updated_at=gear.source.source_updated_at,
                )
                self.session.add(new_source)
                await self.session.flush()
                new_gear.source_id = new_source.id

            # Add tags
            await self._update_tags(new_gear, gear.tags)

            # Add models
            for model_vo in gear.models:
                new_model = GearModel(
                    id=model_vo.id,
                    gear_id=new_gear.id,
                    platform=model_vo.platform,
                    size=model_vo.size,
                    file_path=model_vo.file_path,
                    download_url=model_vo.download_url,
                    download_status=model_vo.download_status,
                    file_hash=model_vo.file_hash,
                )
                self.session.add(new_model)

        await self.session.flush()

    async def delete(self, gear_id: UUID) -> None:
        """Delete gear by ID.

        Args:
            gear_id: The gear's UUID
        """
        gear = await self.session.get(Gear, gear_id)
        if gear:
            await self.session.delete(gear)
            await self.session.flush()

    async def _update_tags(self, gear: Gear, tag_names: list[str]) -> None:
        """Update tags for a gear item.

        Args:
            gear: The ORM Gear model
            tag_names: List of tag names
        """
        # Delete existing tag associations
        delete_stmt = delete(gear_tags_table).where(
            gear_tags_table.c.gear_id == gear.id
        )
        await self.session.execute(delete_stmt)

        # Get or create tags and add associations
        for tag_name in tag_names:
            stmt = select(GearTag).where(GearTag.name == tag_name.lower())
            result = await self.session.execute(stmt)
            tag = result.scalar_one_or_none()

            if not tag:
                tag = GearTag(name=tag_name.lower())
                self.session.add(tag)
                await self.session.flush()

            # Insert into junction table
            insert_stmt = gear_tags_table.insert().values(
                gear_id=gear.id,
                tag_id=tag.id,
            )
            await self.session.execute(insert_stmt)

    async def _update_models(
        self,
        gear: Gear,
        model_vos: list[GearModelVO],
    ) -> None:
        """Update models for a gear item.

        Args:
            gear: The ORM Gear model
            model_vos: List of model value objects
        """
        # Get existing model IDs
        existing_ids = {model.id for model in gear.models}
        new_ids = {model.id for model in model_vos}

        # Delete removed models
        models_to_delete = [
            model for model in gear.models if model.id not in new_ids
        ]
        for model in models_to_delete:
            await self.session.delete(model)

        # Update or create models
        for model_vo in model_vos:
            if model_vo.id in existing_ids:
                # Update existing model
                existing_model = next(
                    m for m in gear.models if m.id == model_vo.id
                )
                existing_model.platform = model_vo.platform
                existing_model.size = model_vo.size
                existing_model.file_path = model_vo.file_path
                existing_model.download_url = model_vo.download_url
                existing_model.download_status = model_vo.download_status
                existing_model.file_hash = model_vo.file_hash
            else:
                # Create new model
                new_model = GearModel(
                    id=model_vo.id,
                    gear_id=gear.id,
                    platform=model_vo.platform,
                    size=model_vo.size,
                    file_path=model_vo.file_path,
                    download_url=model_vo.download_url,
                    download_status=model_vo.download_status,
                    file_hash=model_vo.file_hash,
                )
                self.session.add(new_model)

    def _to_entity(self, gear: Gear) -> GearEntity:
        """Convert ORM Gear to domain GearEntity.

        Args:
            gear: The ORM Gear model

        Returns:
            The domain GearEntity
        """
        # Convert source
        source = None
        if gear.source:
            source = GearSourceVO(
                source_name=gear.source.source_name,
                source_record_id=gear.source.source_record_id,
                source_updated_at=gear.source.source_updated_at,
            )

        # Convert models
        models = [
            GearModelVO(
                id=model.id,
                platform=model.platform,
                size=model.size,
                file_path=model.file_path,
                download_url=model.download_url,
                download_status=model.download_status,
                file_hash=model.file_hash,
            )
            for model in gear.models
        ]

        # Convert tags
        tags = [tag.name for tag in gear.tags]

        return GearEntity(
            id=gear.id,
            name=gear.name,
            slug=gear.slug,
            gear_type=gear.gear_type,
            description=gear.description,
            manufacturer=gear.manufacturer,
            tags=tags,
            source=source,
            models=models,
            thumbnail_url=gear.thumbnail_url,
            is_public=gear.is_public,
            created_at=gear.created_at,
            updated_at=gear.updated_at,
        )
