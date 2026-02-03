"""Base entity class for domain layer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def new_id() -> UUID:
    """Generate a new UUID for entity identification."""
    return uuid4()


def utcnow() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(UTC)


@dataclass(eq=False, slots=True)
class Entity:
    """Base class for domain entities.

    Entities are objects with identity that persists over time.
    Two entities are equal if they have the same ID, regardless
    of their other attributes.

    Attributes:
        id: Unique identifier for the entity
        created_at: When the entity was created
        updated_at: When the entity was last updated
    """

    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same ID."""
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash by ID for use in sets and dicts."""
        return hash(self.id)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = utcnow()
