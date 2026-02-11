"""T3K-specific domain entities.

These entities represent gear data as it exists in the Tone3000 system,
before transformation to GTS format. They are NOT part of the core domain.

All entities are frozen dataclasses with slots for memory efficiency
and immutability.
"""

from dataclasses import dataclass
from datetime import datetime

from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


@dataclass(frozen=True, slots=True)
class T3KCreator:
    """T3K creator/user entity.

    Represents a content creator on the Tone3000 platform.

    Attributes:
        id: T3K creator ID
        username: T3K username
        display_name: Display name
        avatar_url: Profile image URL
        profile_url: Full profile URL
    """

    id: str
    username: str
    display_name: str
    avatar_url: str
    profile_url: str


@dataclass(frozen=True, slots=True)
class T3KPack:
    """T3K pack entity.

    Represents a pack of models on the Tone3000 platform.
    A pack contains one or more models and belongs to a creator.

    Attributes:
        id: T3K pack ID
        name: Pack name
        slug: URL-friendly slug
        creator_id: ID of the creator who owns this pack
        description: Pack description
        thumbnail_url: Pack thumbnail image URL
        platform: Platform type (NAM, AIDA-X, IR)
        pack_type: Pack type (amp, pedal, ir)
        created_at: When the pack was created
        updated_at: When the pack was last updated
    """

    id: str
    name: str
    slug: str
    creator_id: str
    description: str
    thumbnail_url: str
    platform: T3KPlatform
    pack_type: T3KPackType
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class T3KModel:
    """T3K model entity.

    Represents a single model file within a pack on the Tone3000 platform.

    Attributes:
        id: T3K model ID
        pack_id: ID of the pack this model belongs to
        name: Model name
        filename: Model filename
        file_size: File size in bytes
        download_url: URL to download the model file
        checksum: File checksum for integrity verification
        created_at: When the model was created
        updated_at: When the model was last updated
    """

    id: str
    pack_id: str
    name: str
    filename: str
    file_size: int
    download_url: str
    checksum: str
    created_at: datetime
    updated_at: datetime
