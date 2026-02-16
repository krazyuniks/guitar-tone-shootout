"""T3K-specific domain entities.

These entities represent gear data as it exists in the Tone3000 system,
before transformation to GTS format. They are NOT part of the core domain.

All entities are frozen dataclasses with slots for memory efficiency
and immutability.
"""

from dataclasses import dataclass
from datetime import datetime

from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform


@dataclass(frozen=True, slots=True)
class T3KUser:
    """T3K user entity.

    Represents a user on the Tone3000 platform.
    """

    id: str
    username: str
    avatar_url: str
    bio: str
    url: str


@dataclass(frozen=True, slots=True)
class T3KTone:
    """T3K tone entity.

    Represents a tone (formerly "pack") on the Tone3000 platform.
    A tone contains one or more models and belongs to a user.
    """

    id: int
    title: str
    description: str
    tags: list[str]
    makes: list[str]
    gear: T3KGearKind
    platform: T3KPlatform
    models_count: int
    favorites_count: int
    downloads_count: int
    images: list[str]
    user_id: str
    user: T3KUser | None
    url: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class T3KModel:
    """T3K model entity.

    Represents a single model file within a tone on the Tone3000 platform.
    """

    id: int
    tone_id: int
    user_id: str
    name: str
    model_url: str
    size: str
    created_at: datetime
    updated_at: datetime
