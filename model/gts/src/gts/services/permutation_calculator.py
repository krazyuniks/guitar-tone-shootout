"""Permutation calculator service.

Calculates signal chain permutations for group comparisons.
"""

from itertools import product
from uuid import UUID

from gts.domain.entities.signal_chain_group import SignalChainGroup


class PermutationCalculator:
    """Service for calculating signal chain permutations.

    Given a SignalChainGroup with variable slots and gear options,
    this service calculates all valid permutations for comparison.
    """

    def calculate_permutations(
        self,
        group: SignalChainGroup,
    ) -> list[dict[int, UUID | None]]:
        """Calculate all permutations for a group.

        Args:
            group: The signal chain group to permute

        Returns:
            List of permutations, where each permutation is a dict
            mapping slot position to gear ID (or None for empty slot)

        Raises:
            ValueError: If group configuration is invalid
        """
        errors = group.validate()
        if errors:
            raise ValueError(f"Invalid group configuration: {'; '.join(errors)}")

        # Build options per slot
        slot_options: list[list[UUID | None]] = []

        for position in group.slot_positions:
            options: list[UUID | None] = list(group.gear_options.get(position, []))

            if group.include_null:
                options.append(None)  # Add "no gear" option

            slot_options.append(options)

        # Generate all combinations
        if not slot_options:
            return []

        permutations: list[dict[int, UUID | None]] = []

        for combo in product(*slot_options):
            perm: dict[int, UUID | None] = {}
            for i, position in enumerate(group.slot_positions):
                perm[position] = combo[i]
            permutations.append(perm)

        return permutations

    def calculate_permutation_count(self, group: SignalChainGroup) -> int:
        """Calculate the number of permutations without generating them.

        Args:
            group: The signal chain group

        Returns:
            Number of permutations
        """
        return group.estimated_permutation_count()

    def generate_labels(
        self,
        permutations: list[dict[int, UUID | None]],
        gear_names: dict[UUID, str],
        null_label: str = "None",
    ) -> list[str]:
        """Generate human-readable labels for permutations.

        Args:
            permutations: List of permutations from calculate_permutations
            gear_names: Mapping of gear IDs to display names
            null_label: Label for empty slots

        Returns:
            List of labels, one per permutation
        """
        labels: list[str] = []

        for perm in permutations:
            parts: list[str] = []
            for position in sorted(perm.keys()):
                gear_id = perm[position]
                if gear_id is None:
                    parts.append(null_label)
                else:
                    parts.append(gear_names.get(gear_id, str(gear_id)[:8]))
            labels.append(" + ".join(parts))

        return labels

    def filter_duplicate_permutations(
        self,
        permutations: list[dict[int, UUID | None]],
    ) -> list[dict[int, UUID | None]]:
        """Remove duplicate permutations.

        Two permutations are considered duplicates if they have
        the same gear at each position.

        Args:
            permutations: List of permutations

        Returns:
            Deduplicated list
        """
        seen: set[tuple[tuple[int, UUID | None], ...]] = set()
        unique: list[dict[int, UUID | None]] = []

        for perm in permutations:
            key = tuple(sorted(perm.items()))
            if key not in seen:
                seen.add(key)
                unique.append(perm)

        return unique

    def validate_permutation(
        self,
        permutation: dict[int, UUID | None],
        group: SignalChainGroup,
    ) -> list[str]:
        """Validate a single permutation against group rules.

        Args:
            permutation: The permutation to validate
            group: The group it belongs to

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Check all positions are valid slots
        for position in permutation:
            if position not in group.slot_positions:
                errors.append(f"Position {position} is not a variable slot")

        # Check all gear IDs are valid options
        for position, gear_id in permutation.items():
            if gear_id is None:
                if not group.include_null:
                    errors.append(f"Position {position}: null not allowed")
            else:
                options = group.gear_options.get(position, [])
                if gear_id not in options:
                    errors.append(f"Position {position}: gear {gear_id} not in options")

        return errors
