"""BlockType entity for domain layer.

Built-in processor block templates that users can add to signal chains.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow
from core.domain.value_objects.block_category import BlockCategory


@dataclass(eq=False, slots=True)
class BlockType(Entity):
    """Entity representing a built-in processor block type.

    BlockTypes are templates for effects/processors that can be
    added to signal chains. They define the category, parameters,
    and defaults for each block type.

    Attributes:
        id: Unique identifier
        name: Display name (e.g., "Parametric EQ", "Noise Gate")
        category: Block category for ordering rules
        description: Optional description
        icon: Optional icon identifier
        default_params: Default parameter values as dict
        param_schema: JSON Schema for parameters
        is_active: Whether this block type is available
        sort_order: Order for display in UI
        created_at: When created
        updated_at: When last updated
    """

    name: str = ""
    category: BlockCategory = BlockCategory.UTILITY
    description: str | None = None
    icon: str | None = None
    default_params: dict[str, float | int | str | bool] = field(default_factory=dict)
    param_schema: dict[str, object] = field(default_factory=dict)
    is_active: bool = True
    sort_order: int = 0
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def is_pre_amp(self) -> bool:
        """Check if this block type is valid in pre-amp position."""
        from core.domain.value_objects.block_category import PRE_AMP_CATEGORIES
        return self.category in PRE_AMP_CATEGORIES

    def is_post_amp(self) -> bool:
        """Check if this block type is valid in post-amp position."""
        from core.domain.value_objects.block_category import POST_AMP_CATEGORIES
        return self.category in POST_AMP_CATEGORIES

    def get_default_param(self, param_name: str) -> float | int | str | bool | None:
        """Get a default parameter value.

        Args:
            param_name: The parameter name

        Returns:
            The default value or None if not found
        """
        return self.default_params.get(param_name)

    def activate(self) -> None:
        """Activate the block type."""
        self.is_active = True
        self.updated_at = utcnow()

    def deactivate(self) -> None:
        """Deactivate the block type."""
        self.is_active = False
        self.updated_at = utcnow()
