"""Permutation processing for signal chain groups.

Expands SignalChainGroup permutations using the domain PermutationCalculator.
"""

from uuid import UUID

from core.domain.entities.signal_chain_group import SignalChainGroup
from core.services.permutation_calculator import PermutationCalculator


class PermutationError(Exception):
    """Error during permutation processing."""

    pass


def expand_signal_chain_group(
    group: SignalChainGroup,
) -> list[dict[int, UUID | None]]:
    """Expand a signal chain group into all permutations.

    Uses the domain PermutationCalculator to generate all valid permutations
    with proper limit enforcement.

    Args:
        group: The signal chain group to expand

    Returns:
        List of permutations, where each permutation is a dict
        mapping slot position to gear ID (or None for empty slot)

    Raises:
        PermutationError: If group configuration is invalid or exceeds limits
    """
    calculator = PermutationCalculator()

    try:
        permutations: list[dict[int, UUID | None]] = calculator.calculate_permutations(group)
    except ValueError as e:
        raise PermutationError(str(e)) from e

    return permutations


def generate_permutation_labels(
    permutations: list[dict[int, UUID | None]],
    gear_names: dict[UUID, str],
    null_label: str = "None",
) -> list[str]:
    """Generate human-readable labels for permutations.

    Args:
        permutations: List of permutations from expand_signal_chain_group
        gear_names: Mapping of gear IDs to display names
        null_label: Label for empty slots (default: "None")

    Returns:
        List of labels, one per permutation
    """
    calculator = PermutationCalculator()
    labels: list[str] = calculator.generate_labels(permutations, gear_names, null_label)
    return labels
