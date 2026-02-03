"""SignalChainGroup entity for domain layer.

Groups of signal chains for permutation-based comparisons.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow


@dataclass(eq=False, slots=True)
class SignalChainGroup(Entity):
    """Entity representing a group of signal chains for comparison.

    Groups allow users to compare multiple gear options at specific
    positions in a chain. The system generates permutations to test
    all combinations.

    Example: Compare 3 amps with 2 cabs = 6 permutations

    Attributes:
        id: Unique identifier
        user_id: Owner's user ID
        name: Display name for the group
        description: Optional description
        base_chain_id: The base signal chain to vary
        slot_positions: Positions in the chain that can vary
        gear_options: Gear options per slot (slot_index -> gear_ids)
        include_null: Whether to include "no gear" as an option
        max_permutations: Maximum permutations to generate
        created_at: When created
        updated_at: When last updated
    """

    MAX_PERMUTATIONS = 27  # 3^3 - sensible limit

    user_id: UUID = field(default_factory=new_id)
    name: str = ""
    description: str | None = None
    base_chain_id: UUID | None = None
    slot_positions: list[int] = field(default_factory=list)
    gear_options: dict[int, list[UUID]] = field(default_factory=dict)
    include_null: bool = False
    max_permutations: int = MAX_PERMUTATIONS
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def add_slot(self, position: int) -> None:
        """Add a variable slot position.

        Args:
            position: The chain position that can vary
        """
        if position not in self.slot_positions:
            self.slot_positions.append(position)
            self.slot_positions.sort()
            self.gear_options[position] = []
            self.updated_at = utcnow()

    def remove_slot(self, position: int) -> bool:
        """Remove a variable slot position.

        Args:
            position: The position to remove

        Returns:
            True if removed, False if not found
        """
        if position in self.slot_positions:
            self.slot_positions.remove(position)
            self.gear_options.pop(position, None)
            self.updated_at = utcnow()
            return True
        return False

    def add_gear_option(self, position: int, gear_id: UUID) -> None:
        """Add a gear option for a slot.

        Args:
            position: The slot position
            gear_id: The gear ID to add as an option

        Raises:
            ValueError: If position is not a variable slot
        """
        if position not in self.slot_positions:
            raise ValueError(f"Position {position} is not a variable slot")

        if gear_id not in self.gear_options[position]:
            self.gear_options[position].append(gear_id)
            self.updated_at = utcnow()

    def remove_gear_option(self, position: int, gear_id: UUID) -> bool:
        """Remove a gear option from a slot.

        Args:
            position: The slot position
            gear_id: The gear ID to remove

        Returns:
            True if removed, False if not found
        """
        if position in self.gear_options:
            options = self.gear_options[position]
            if gear_id in options:
                options.remove(gear_id)
                self.updated_at = utcnow()
                return True
        return False

    def get_option_counts(self) -> list[int]:
        """Get the number of options per slot.

        Returns:
            List of option counts, one per slot
        """
        counts = []
        for pos in self.slot_positions:
            count = len(self.gear_options.get(pos, []))
            if self.include_null:
                count += 1  # Add 1 for the "no gear" option
            counts.append(count)
        return counts

    def estimated_permutation_count(self) -> int:
        """Estimate the number of permutations.

        Returns:
            Estimated permutation count (product of option counts)
        """
        counts = self.get_option_counts()
        if not counts:
            return 0

        result = 1
        for count in counts:
            result *= max(count, 1)
        return result

    def exceeds_max_permutations(self) -> bool:
        """Check if permutations would exceed the limit.

        Returns:
            True if estimated count exceeds max_permutations
        """
        return self.estimated_permutation_count() > self.max_permutations

    def validate(self) -> list[str]:
        """Validate the group configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if not self.base_chain_id:
            errors.append("Base chain is required")

        if not self.slot_positions:
            errors.append("At least one variable slot is required")

        for pos in self.slot_positions:
            options = self.gear_options.get(pos, [])
            min_options = 0 if self.include_null else 1
            if len(options) < min_options:
                errors.append(f"Slot at position {pos} needs at least {min_options} option(s)")

        if self.exceeds_max_permutations():
            errors.append(
                f"Too many permutations ({self.estimated_permutation_count()}). "
                f"Maximum is {self.max_permutations}."
            )

        return errors

    def is_valid(self) -> bool:
        """Check if the group is valid.

        Returns:
            True if valid, False otherwise
        """
        return len(self.validate()) == 0
