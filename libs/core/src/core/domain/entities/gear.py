"""Gear entity for domain layer.

Unified gear model that abstracts away source-specific details.
Gear can come from multiple sources (T3K, user uploads, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow
from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform


@dataclass(frozen=True, slots=True)
class GearSource:
    """Value object representing the source of gear data.

    Tracks where gear came from for sync and attribution.

    Attributes:
        source_name: Name of the source (e.g., 't3k', 'user_upload')
        source_record_id: ID in the source system
        source_updated_at: Last update time in source system
    """

    source_name: str
    source_record_id: str
    source_updated_at: datetime


@dataclass(frozen=True, slots=True)
class GearModel:
    """Value object representing a downloadable model file.

    A piece of gear can have multiple model files (different sizes,
    formats, etc.)

    Attributes:
        id: Unique identifier for this model
        platform: Target platform (NAM, AIDA-X, etc.)
        size: Model size variant (standard, lite, etc.)
        file_path: Local path to model file (if downloaded)
        download_url: URL to download the model
        download_status: Current download status
        file_hash: SHA256 hash for integrity verification
    """

    id: UUID
    platform: Platform
    size: ModelSize
    file_path: str | None = None
    download_url: str | None = None
    download_status: DownloadStatus = DownloadStatus.PENDING
    file_hash: str | None = None

    def is_available(self) -> bool:
        """Check if the model is available for use."""
        return (
            self.download_status == DownloadStatus.COMPLETED
            and self.file_path is not None
        )


@dataclass(eq=False, slots=True)
class Gear(Entity):
    """Domain entity representing a piece of gear.

    Unified representation of amps, pedals, IRs, etc. from any source.
    This is the core domain's view of gear - source-specific details
    are handled by source adapters.

    Attributes:
        id: Unique internal identifier
        name: Display name
        slug: URL-friendly identifier
        gear_type: Type of gear (amp, pedal, ir, etc.)
        description: Optional description
        manufacturer: Gear manufacturer
        tags: List of tags for categorisation
        source: Where the gear came from
        models: Available model files
        thumbnail_url: Preview image URL
        is_public: Whether visible to all users
        created_at: When created in GTS
        updated_at: When last updated in GTS
    """

    name: str = ""
    slug: str = ""
    gear_type: GearType = GearType.AMP
    description: str | None = None
    manufacturer: str | None = None
    tags: list[str] = field(default_factory=list)
    source: GearSource | None = None
    models: list[GearModel] = field(default_factory=list)
    thumbnail_url: str | None = None
    is_public: bool = True
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def get_model(
        self,
        platform: Platform,
        size: ModelSize = ModelSize.STANDARD,
    ) -> GearModel | None:
        """Get a specific model variant.

        Args:
            platform: Target platform
            size: Model size variant

        Returns:
            The matching GearModel if found, None otherwise
        """
        for model in self.models:
            if model.platform == platform and model.size == size:
                return model
        return None

    def get_available_model(self, platform: Platform) -> GearModel | None:
        """Get any available model for a platform.

        Tries standard size first, then others.

        Args:
            platform: Target platform

        Returns:
            An available GearModel if found, None otherwise
        """
        # Try standard first
        for size in [ModelSize.STANDARD, ModelSize.LITE, ModelSize.FEATHER, ModelSize.NANO]:
            model = self.get_model(platform, size)
            if model and model.is_available():
                return model
        return None

    def has_tag(self, tag: str) -> bool:
        """Check if gear has a specific tag.

        Args:
            tag: Tag to check (case-insensitive)

        Returns:
            True if the tag exists
        """
        tag_lower = tag.lower()
        return any(t.lower() == tag_lower for t in self.tags)

    def add_model(self, model: GearModel) -> None:
        """Add a model variant.

        Args:
            model: The model to add
        """
        self.models.append(model)
        self.updated_at = utcnow()


@dataclass(eq=False, slots=True)
class UserGear(Entity):
    """Entity representing gear in a user's library.

    Links a user to gear they've added to their collection.
    This allows users to have their own copy of public gear
    with personalised settings.

    Attributes:
        id: Unique identifier for this user-gear link
        user_id: Owner's user ID
        gear_id: Reference to the Gear entity
        nickname: User's custom name for this gear
        notes: User's notes about this gear
        is_favourite: Whether marked as favourite
        created_at: When added to library
        updated_at: When last updated
    """

    user_id: UUID = field(default_factory=new_id)
    gear_id: UUID = field(default_factory=new_id)
    nickname: str | None = None
    notes: str | None = None
    is_favourite: bool = False
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def set_nickname(self, nickname: str | None) -> None:
        """Set a custom nickname.

        Args:
            nickname: Custom name or None to clear
        """
        self.nickname = nickname
        self.updated_at = utcnow()

    def toggle_favourite(self) -> bool:
        """Toggle favourite status.

        Returns:
            New favourite status
        """
        self.is_favourite = not self.is_favourite
        self.updated_at = utcnow()
        return self.is_favourite
