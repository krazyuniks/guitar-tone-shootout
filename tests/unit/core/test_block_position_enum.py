"""Unit tests for BlockPosition value object."""

import pytest

from gts.domain.value_objects.block_position import BlockPosition


def test_block_position_enum_exists() -> None:
    """Test that BlockPosition enum is defined."""
    assert BlockPosition is not None


def test_block_position_has_pre_value() -> None:
    """Test that BlockPosition has PRE value for pre-amp position."""
    assert hasattr(BlockPosition, "PRE")
    assert BlockPosition.PRE.value == "pre"


def test_block_position_has_loop_value() -> None:
    """Test that BlockPosition has LOOP value for effects loop position."""
    assert hasattr(BlockPosition, "LOOP")
    assert BlockPosition.LOOP.value == "loop"


def test_block_position_has_post_value() -> None:
    """Test that BlockPosition has POST value for post-amp position."""
    assert hasattr(BlockPosition, "POST")
    assert BlockPosition.POST.value == "post"


def test_block_position_all_values() -> None:
    """Test that BlockPosition has exactly the three expected values."""
    expected_values = {"pre", "loop", "post"}
    actual_values = {position.value for position in BlockPosition}
    assert actual_values == expected_values


def test_block_position_from_string() -> None:
    """Test creating BlockPosition from string value."""
    assert BlockPosition("pre") == BlockPosition.PRE
    assert BlockPosition("loop") == BlockPosition.LOOP
    assert BlockPosition("post") == BlockPosition.POST


def test_block_position_invalid_value() -> None:
    """Test that invalid BlockPosition value raises ValueError."""
    with pytest.raises(ValueError, match="'invalid'"):
        BlockPosition("invalid")
