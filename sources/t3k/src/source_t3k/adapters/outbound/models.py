"""SQLAlchemy ORM models for T3K staging tables.

These models live in gts_core using t3k_* table prefixes.
They are used to stage T3K data before transformation to unified core records.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, MetaData, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser
from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform

# Naming conventions for database constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class for T3K staging tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class T3KUserStaging(Base):
    """Staging table for T3K users."""

    __tablename__ = "t3k_users_staging"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")

    @classmethod
    def from_domain(cls, entity: T3KUser) -> "T3KUserStaging":
        return cls(
            id=entity.id,
            username=entity.username,
            avatar_url=entity.avatar_url,
            bio=entity.bio,
            url=entity.url,
        )

    def to_domain(self) -> T3KUser:
        return T3KUser(
            id=self.id,
            username=self.username,
            avatar_url=self.avatar_url,
            bio=self.bio,
            url=self.url,
        )


class T3KToneStaging(Base):
    """Staging table for T3K tones (formerly packs)."""

    __tablename__ = "t3k_tones_staging"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    makes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    gear: Mapped[str] = mapped_column(String(50), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    models_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorites_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloads_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    images: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Updated each time the tone is re-synced from the T3K API. Serves as a
    # tombstone detection signal: tones deleted from T3K will have increasingly
    # stale last_synced_at values compared to active tones.
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_domain(cls, entity: T3KTone) -> "T3KToneStaging":
        return cls(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            tags=entity.tags,
            makes=entity.makes,
            gear=entity.gear.value,
            platform=entity.platform.value,
            models_count=entity.models_count,
            favorites_count=entity.favorites_count,
            downloads_count=entity.downloads_count,
            images=entity.images,
            user_id=entity.user_id,
            url=entity.url,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_domain(self) -> T3KTone:
        return T3KTone(
            id=self.id,
            title=self.title,
            description=self.description,
            tags=self.tags,
            makes=self.makes,
            gear=T3KGearKind(self.gear),
            platform=T3KPlatform(self.platform),
            models_count=self.models_count,
            favorites_count=self.favorites_count,
            downloads_count=self.downloads_count,
            images=self.images,
            user_id=self.user_id,
            user=None,
            url=self.url,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class T3KModelStaging(Base):
    """Staging table for T3K models."""

    __tablename__ = "t3k_models_staging"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    tone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_domain(cls, entity: T3KModel) -> "T3KModelStaging":
        return cls(
            id=entity.id,
            tone_id=entity.tone_id,
            user_id=entity.user_id,
            name=entity.name,
            model_url=entity.model_url,
            size=entity.size,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_domain(self) -> T3KModel:
        return T3KModel(
            id=self.id,
            tone_id=self.tone_id,
            user_id=self.user_id,
            name=self.name,
            model_url=self.model_url,
            size=self.size,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class SyncCheckpoint(Base):
    """Tracks synchronisation progress for T3K entities."""

    __tablename__ = "t3k_sync_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    total_synced: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "entity_type",
            name="uq_t3k_sync_checkpoints_source_entity",
        ),
    )
