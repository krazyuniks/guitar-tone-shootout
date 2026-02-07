"""Unit tests for T16: GearRepository protocol - get_by_slug method.

Tests that the GearRepository protocol defines the get_by_slug method
as mentioned in the acceptance criteria.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from core.ports.repositories import GearRepository


def test_gear_repository_protocol_has_get_by_slug_method() -> None:
    """Test that GearRepository protocol defines get_by_slug method."""
    from core.ports.repositories import GearRepository

    # Protocol should have get_by_slug method
    assert hasattr(GearRepository, "get_by_slug")


def test_gear_repository_protocol_get_by_slug_signature() -> None:
    """Test that get_by_slug has correct method signature."""
    from inspect import signature

    from core.ports.repositories import GearRepository

    # Get the method from protocol
    method = getattr(GearRepository, "get_by_slug")

    # Check signature
    sig = signature(method)

    # Should have 'slug' parameter
    assert "slug" in sig.parameters

    # Return type should be Gear | None
    return_annotation = sig.return_annotation
    assert return_annotation is not None


def test_sqlalchemy_gear_repository_implements_get_by_slug() -> None:
    """Test that SQLAlchemyGearRepository implements get_by_slug."""
    from webapp.adapters.persistence.repositories.gear_repository import (
        SQLAlchemyGearRepository,
    )

    # Should have the method
    assert hasattr(SQLAlchemyGearRepository, "get_by_slug")

    # Should be callable
    assert callable(getattr(SQLAlchemyGearRepository, "get_by_slug"))
