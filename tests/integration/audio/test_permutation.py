"""Integration tests for permutation processing.

Tests Cartesian product generation from SignalChainGroup with null handling
and limit enforcement.
"""

from uuid import UUID, uuid4

import pytest

from audio.processing.permutation import (
    PermutationError,
    expand_signal_chain_group,
    generate_permutation_labels,
)
from core.domain.entities.signal_chain_group import SignalChainGroup


@pytest.fixture
def simple_group() -> SignalChainGroup:
    """Create a simple group with 2 slots, 2 options each."""
    group = SignalChainGroup(
        user_id=uuid4(),
        name="Simple Group",
        base_chain_id=uuid4(),
    )

    # Slot 0: 2 amp options
    group.add_slot(0)
    amp1 = uuid4()
    amp2 = uuid4()
    group.add_gear_option(0, amp1)
    group.add_gear_option(0, amp2)

    # Slot 1: 2 cab options
    group.add_slot(1)
    cab1 = uuid4()
    cab2 = uuid4()
    group.add_gear_option(1, cab1)
    group.add_gear_option(1, cab2)

    return group


@pytest.fixture
def group_with_null() -> SignalChainGroup:
    """Create a group with include_null enabled."""
    group = SignalChainGroup(
        user_id=uuid4(),
        name="Group with Null",
        base_chain_id=uuid4(),
        include_null=True,
    )

    # Slot 0: 2 options
    group.add_slot(0)
    gear1 = uuid4()
    gear2 = uuid4()
    group.add_gear_option(0, gear1)
    group.add_gear_option(0, gear2)

    return group


@pytest.fixture
def group_at_limit() -> SignalChainGroup:
    """Create a group exactly at the 27 permutation limit (3x3x3)."""
    group = SignalChainGroup(
        user_id=uuid4(),
        name="At Limit",
        base_chain_id=uuid4(),
    )

    # 3 slots with 3 options each = 27 permutations
    for slot in range(3):
        group.add_slot(slot)
        for _ in range(3):
            group.add_gear_option(slot, uuid4())

    return group


@pytest.fixture
def group_exceeds_limit() -> SignalChainGroup:
    """Create a group that exceeds the 27 permutation limit."""
    group = SignalChainGroup(
        user_id=uuid4(),
        name="Exceeds Limit",
        base_chain_id=uuid4(),
    )

    # 3 slots with 4 options each = 64 permutations (exceeds 27)
    for slot in range(3):
        group.add_slot(slot)
        for _ in range(4):
            group.add_gear_option(slot, uuid4())

    return group


def test_expand_simple_group(simple_group: SignalChainGroup) -> None:
    """Test basic Cartesian product generation."""
    permutations = expand_signal_chain_group(simple_group)

    # 2 amps x 2 cabs = 4 permutations
    assert len(permutations) == 4

    # All permutations should have 2 positions
    for perm in permutations:
        assert len(perm) == 2
        assert 0 in perm
        assert 1 in perm
        assert isinstance(perm[0], UUID)
        assert isinstance(perm[1], UUID)


def test_expand_group_with_null(group_with_null: SignalChainGroup) -> None:
    """Test null gear handling (with/without effect comparisons)."""
    permutations = expand_signal_chain_group(group_with_null)

    # 2 options + None = 3 permutations
    assert len(permutations) == 3

    # Check that None appears in some permutations
    null_count = sum(1 for perm in permutations if perm[0] is None)
    assert null_count == 1

    # Check that valid UUIDs appear in others
    uuid_count = sum(1 for perm in permutations if isinstance(perm[0], UUID))
    assert uuid_count == 2


def test_expand_group_at_limit(group_at_limit: SignalChainGroup) -> None:
    """Test that groups at the 27 permutation limit work correctly."""
    permutations = expand_signal_chain_group(group_at_limit)

    # Should generate exactly 27 permutations
    assert len(permutations) == 27

    # All permutations should have 3 positions
    for perm in permutations:
        assert len(perm) == 3


def test_expand_group_exceeds_limit_raises_error(group_exceeds_limit: SignalChainGroup) -> None:
    """Test that groups exceeding the limit raise PermutationError."""
    with pytest.raises(PermutationError, match="Too many permutations"):
        expand_signal_chain_group(group_exceeds_limit)


def test_expand_invalid_group_raises_error() -> None:
    """Test that invalid groups raise PermutationError."""
    # Group without base_chain_id
    invalid_group = SignalChainGroup(
        user_id=uuid4(),
        name="Invalid",
    )
    invalid_group.add_slot(0)
    invalid_group.add_gear_option(0, uuid4())

    with pytest.raises(PermutationError, match="Base chain is required"):
        expand_signal_chain_group(invalid_group)


def test_generate_permutation_labels_basic() -> None:
    """Test basic label generation for permutations."""
    # Create permutations manually
    gear1 = uuid4()
    gear2 = uuid4()

    permutations = [
        {0: gear1, 1: gear2},
        {0: gear2, 1: gear1},
        {0: None, 1: gear1},
    ]

    gear_names = {
        gear1: "Marshall JCM800",
        gear2: "Fender Twin",
    }

    labels = generate_permutation_labels(permutations, gear_names)

    assert len(labels) == 3
    assert labels[0] == "Marshall JCM800 + Fender Twin"
    assert labels[1] == "Fender Twin + Marshall JCM800"
    assert labels[2] == "None + Marshall JCM800"


def test_generate_permutation_labels_custom_null_label() -> None:
    """Test label generation with custom null label."""
    gear1 = uuid4()

    permutations = [
        {0: gear1},
        {0: None},
    ]

    gear_names = {gear1: "Mesa Boogie"}

    labels = generate_permutation_labels(permutations, gear_names, null_label="No Amp")

    assert labels[0] == "Mesa Boogie"
    assert labels[1] == "No Amp"


def test_permutations_are_unique(simple_group: SignalChainGroup) -> None:
    """Test that all generated permutations are unique."""
    permutations = expand_signal_chain_group(simple_group)

    # Convert to tuples for set comparison
    perm_tuples = [tuple(sorted(perm.items())) for perm in permutations]

    # All should be unique
    assert len(perm_tuples) == len(set(perm_tuples))


def test_permutations_use_domain_calculator(simple_group: SignalChainGroup) -> None:
    """Test that permutations come from domain PermutationCalculator."""
    from core.services.permutation_calculator import PermutationCalculator

    # Calculate directly with domain service
    calculator = PermutationCalculator()
    expected = calculator.calculate_permutations(simple_group)

    # Calculate via audio module
    actual = expand_signal_chain_group(simple_group)

    # Should match
    assert len(actual) == len(expected)

    # Convert both to sets of tuples for comparison
    expected_set = {tuple(sorted(perm.items())) for perm in expected}
    actual_set = {tuple(sorted(perm.items())) for perm in actual}

    assert expected_set == actual_set
