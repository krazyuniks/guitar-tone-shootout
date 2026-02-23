"""ShootoutComment entity for domain layer."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from gts.domain.entities.base import Entity, new_id, utcnow


@dataclass(eq=False, slots=True)
class ShootoutComment(Entity):
    """Entity representing a user comment on a shootout.

    Comments allow users to discuss shootouts. Each comment belongs
    to a shootout and a user.

    Attributes:
        id: Unique identifier
        shootout_id: ID of the shootout this comment belongs to
        user_id: ID of the user who wrote the comment
        content: The comment text
        created_at: When the comment was created
        updated_at: When the comment was last updated
    """

    shootout_id: UUID = field(default_factory=new_id)
    user_id: UUID = field(default_factory=new_id)
    content: str = ""
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
