"""Test that all ORM relationships enforce lazy='raise' to prevent N+1 queries.

This test verifies that every relationship in the ORM layer uses lazy='raise',
which forces repositories to explicitly specify eager loading strategies.

See: .claude/rules/query-patterns.md
"""

import inspect
from typing import get_args

import pytest
from sqlalchemy.orm import Mapped, RelationshipProperty

from webapp.adapters.persistence.models import (
    AudioSegment,
    BlockType,
    DITrack,
    Gear,
    GearMake,
    GearModel,
    GearSource,
    GearTag,
    Job,
    OAuthProvider,
    Preset,
    Shootout,
    ShootoutChain,
    SignalChain,
    SignalChainBlock,
    SignalChainGroup,
    User,
    UserGear,
    UserIdentity,
)

# All models that have relationships
ALL_MODELS = [
    AudioSegment,
    BlockType,
    DITrack,
    Gear,
    GearMake,
    GearModel,
    GearSource,
    GearTag,
    Job,
    OAuthProvider,
    Preset,
    Shootout,
    ShootoutChain,
    SignalChain,
    SignalChainBlock,
    SignalChainGroup,
    User,
    UserGear,
    UserIdentity,
]


def get_relationship_properties(model_class):
    """Extract all relationship properties from a model class.

    Returns:
        dict: Mapping of property name to RelationshipProperty
    """
    relationships = {}
    for name, attr in inspect.getmembers(model_class):
        # Skip private/magic attributes
        if name.startswith("_"):
            continue

        # Check if it's a relationship property
        if hasattr(model_class, name):
            try:
                descriptor = getattr(model_class, name)
                if isinstance(descriptor.property, RelationshipProperty):
                    relationships[name] = descriptor.property
            except AttributeError:
                continue

    return relationships


class TestLazyRaiseEnforcement:
    """Test suite for lazy='raise' enforcement across all ORM models."""

    @pytest.mark.parametrize("model_class", ALL_MODELS, ids=lambda m: m.__name__)
    def test_all_relationships_use_lazy_raise(self, model_class):
        """Verify that all relationships in the model use lazy='raise'."""
        relationships = get_relationship_properties(model_class)

        # Track violations for detailed error message
        violations = []

        for rel_name, rel_prop in relationships.items():
            lazy_strategy = rel_prop.lazy

            # lazy should be exactly 'raise'
            if lazy_strategy != "raise":
                violations.append(
                    f"{model_class.__name__}.{rel_name}: lazy='{lazy_strategy}' (expected 'raise')"
                )

        # Assert no violations found
        if violations:
            violation_msg = "\n".join(f"  - {v}" for v in violations)
            pytest.fail(
                f"Found {len(violations)} relationship(s) without lazy='raise':\n{violation_msg}\n\n"
                f"All relationships must use lazy='raise' to enforce explicit eager loading.\n"
                f"See: .claude/rules/query-patterns.md"
            )

    def test_gear_relationships_all_lazy_raise(self):
        """Verify Gear model relationships (task acceptance criterion)."""
        relationships = get_relationship_properties(Gear)

        expected_relationships = {"make", "source", "models", "tags"}
        actual_relationships = set(relationships.keys())

        # Verify we found all expected relationships
        assert expected_relationships == actual_relationships, (
            f"Gear relationships mismatch. "
            f"Expected: {expected_relationships}, Found: {actual_relationships}"
        )

        # Verify all use lazy='raise'
        for rel_name, rel_prop in relationships.items():
            assert rel_prop.lazy == "raise", (
                f"Gear.{rel_name} must use lazy='raise', found: '{rel_prop.lazy}'"
            )

    def test_user_relationships_all_lazy_raise(self):
        """Verify User model relationships (task acceptance criterion)."""
        relationships = get_relationship_properties(User)

        expected_relationships = {
            "identities",  # forward
            "signal_chains",  # reverse
            "signal_chain_groups",  # reverse
            "di_tracks",  # reverse
            "shootouts",  # reverse
            "jobs",  # reverse
            "user_gear",  # reverse
        }
        actual_relationships = set(relationships.keys())

        # Verify we found all expected relationships
        assert expected_relationships == actual_relationships, (
            f"User relationships mismatch. "
            f"Expected: {expected_relationships}, Found: {actual_relationships}"
        )

        # Verify all use lazy='raise'
        for rel_name, rel_prop in relationships.items():
            assert rel_prop.lazy == "raise", (
                f"User.{rel_name} must use lazy='raise', found: '{rel_prop.lazy}'"
            )

    def test_signal_chain_relationships_all_lazy_raise(self):
        """Verify SignalChain model relationships (task acceptance criterion)."""
        relationships = get_relationship_properties(SignalChain)

        expected_relationships = {"user", "blocks"}
        actual_relationships = set(relationships.keys())

        # Verify we found all expected relationships
        assert expected_relationships == actual_relationships, (
            f"SignalChain relationships mismatch. "
            f"Expected: {expected_relationships}, Found: {actual_relationships}"
        )

        # Verify all use lazy='raise'
        for rel_name, rel_prop in relationships.items():
            assert rel_prop.lazy == "raise", (
                f"SignalChain.{rel_name} must use lazy='raise', found: '{rel_prop.lazy}'"
            )

    def test_shootout_relationships_all_lazy_raise(self):
        """Verify Shootout model relationships (task acceptance criterion)."""
        relationships = get_relationship_properties(Shootout)

        expected_relationships = {"user", "di_track", "chains"}
        actual_relationships = set(relationships.keys())

        # Verify we found all expected relationships
        assert expected_relationships == actual_relationships, (
            f"Shootout relationships mismatch. "
            f"Expected: {expected_relationships}, Found: {actual_relationships}"
        )

        # Verify all use lazy='raise'
        for rel_name, rel_prop in relationships.items():
            assert rel_prop.lazy == "raise", (
                f"Shootout.{rel_name} must use lazy='raise', found: '{rel_prop.lazy}'"
            )

    def test_user_identity_relationships_all_lazy_raise(self):
        """Verify UserIdentity model relationships (task acceptance criterion)."""
        relationships = get_relationship_properties(UserIdentity)

        expected_relationships = {"user", "provider"}
        actual_relationships = set(relationships.keys())

        # Verify we found all expected relationships
        assert expected_relationships == actual_relationships, (
            f"UserIdentity relationships mismatch. "
            f"Expected: {expected_relationships}, Found: {actual_relationships}"
        )

        # Verify all use lazy='raise'
        for rel_name, rel_prop in relationships.items():
            assert rel_prop.lazy == "raise", (
                f"UserIdentity.{rel_name} must use lazy='raise', found: '{rel_prop.lazy}'"
            )
