"""Tests that GearType should exist in its own file.

Per task T9 acceptance criteria, GearType enum should be in:
  libs/core/src/core/domain/value_objects/gear_type.py

Currently, GearType is in signal_chain_enums.py.
This test verifies the expected file structure.
"""

import importlib.util


def test_gear_type_has_separate_module() -> None:
    """Test that GearType enum exists in its own module file.

    Per T9 scope:
    - libs/core/src/core/domain/value_objects/gear_type.py

    This file should contain the GearType enum with values:
    AMP, FULL_RIG, PEDAL, OUTBOARD, IR
    """
    # Try to import from the expected location
    spec = importlib.util.find_spec("core.domain.value_objects.gear_type")

    # This will fail because gear_type.py doesn't exist
    assert spec is not None, (
        "GearType should be in its own file: "
        "libs/core/src/core/domain/value_objects/gear_type.py"
    )

    # Verify we can import GearType from it
    import sys
    module = importlib.util.module_from_spec(spec)
    if spec.loader:
        spec.loader.exec_module(module)
    sys.modules["core.domain.value_objects.gear_type"] = module

    assert hasattr(module, "GearType"), (
        "gear_type.py should export GearType enum"
    )

    # Verify the enum has the required values from wiki:304-312
    gear_type_enum = getattr(module, "GearType")
    expected_values = {"AMP", "FULL_RIG", "PEDAL", "OUTBOARD", "IR"}
    actual_values = {member.name for member in gear_type_enum}

    # POST_EFFECT exists in current implementation but wiki specifies 5 types
    # Test for the 5 required types from the acceptance criteria
    assert expected_values.issubset(actual_values), (
        f"GearType should have at least these values: {expected_values}, "
        f"got: {actual_values}"
    )
