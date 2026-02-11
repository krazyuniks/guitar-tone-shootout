"""SQLAlchemy ORM models for T3K staging tables.

These models live in the gts_t3k_source database, separate from gts_core.
They are used to stage T3K data before transformation to GTS format.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from source_t3k.domain.entities import T3KCreator, T3KModel, T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform

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


class T3KCreatorStaging(Base):
    """Staging table for T3K creators.

    Stores creator data from T3K before transformation to GTS User entities.
    """

    __tablename__ = "t3k_creators_staging"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    @classmethod
    def from_domain(cls, entity: T3KCreator) -> "T3KCreatorStaging":
        """Create staging model from domain entity.

        Args:
            entity: T3K creator domain entity

        Returns:
            T3KCreatorStaging instance
        """
        return cls(
            id=entity.id,
            username=entity.username,
            display_name=entity.display_name,
            avatar_url=entity.avatar_url,
            profile_url=entity.profile_url,
        )

    def to_domain(self) -> T3KCreator:
        """Convert staging model to domain entity.

        Returns:
            T3KCreator domain entity
        """
        return T3KCreator(
            id=self.id,
            username=self.username,
            display_name=self.display_name,
            avatar_url=self.avatar_url,
            profile_url=self.profile_url,
        )


class T3KPackStaging(Base):
    """Staging table for T3K packs.

    Stores pack data from T3K before transformation to GTS Gear entities.
    """

    __tablename__ = "t3k_packs_staging"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    creator_id: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    platform: Mapped[T3KPlatform] = mapped_column(String(50), nullable=False)
    pack_type: Mapped[T3KPackType] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_domain(cls, entity: T3KPack) -> "T3KPackStaging":
        """Create staging model from domain entity.

        Args:
            entity: T3K pack domain entity

        Returns:
            T3KPackStaging instance
        """
        return cls(
            id=entity.id,
            name=entity.name,
            slug=entity.slug,
            creator_id=entity.creator_id,
            description=entity.description,
            thumbnail_url=entity.thumbnail_url,
            platform=entity.platform,
            pack_type=entity.pack_type,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_domain(self) -> T3KPack:
        """Convert staging model to domain entity.

        Returns:
            T3KPack domain entity
        """
        return T3KPack(
            id=self.id,
            name=self.name,
            slug=self.slug,
            creator_id=self.creator_id,
            description=self.description,
            thumbnail_url=self.thumbnail_url,
            platform=T3KPlatform(self.platform),
            pack_type=T3KPackType(self.pack_type),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class T3KModelStaging(Base):
    """Staging table for T3K models.

    Stores model data from T3K before transformation to GTS GearModel entities.
    """

    __tablename__ = "t3k_models_staging"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    pack_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    download_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, entity: T3KModel) -> "T3KModelStaging":
        """Create staging model from domain entity.

        Args:
            entity: T3K model domain entity

        Returns:
            T3KModelStaging instance
        """
        return cls(
            id=entity.id,
            pack_id=entity.pack_id,
            name=entity.name,
            filename=entity.filename,
            file_size=entity.file_size,
            download_url=entity.download_url,
            checksum=entity.checksum,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_domain(self) -> T3KModel:
        """Convert staging model to domain entity.

        Returns:
            T3KModel domain entity
        """
        return T3KModel(
            id=self.id,
            pack_id=self.pack_id,
            name=self.name,
            filename=self.filename,
            file_size=self.file_size,
            download_url=self.download_url,
            checksum=self.checksum,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class SyncCheckpoint(Base):
    """Tracks synchronisation progress for T3K entities.

    Used to resume syncs from the last successful point and track metrics.
    """

    __tablename__ = "sync_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    total_synced: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("source_name", "entity_type", name="uq_source_entity"),)


class OAuthToken(Base):
    """Stores encrypted OAuth tokens for T3K API authentication.

    Tokens are encrypted at rest using Fernet encryption. The encryption key
    must be provided via the T3K_TOKEN_ENCRYPTION_KEY environment variable.
    """

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_token_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
