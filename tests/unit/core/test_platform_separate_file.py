"""Tests that Platform should exist in its own file.

Per task T9 acceptance criteria, Platform enum should be in:
  libs/core/src/core/domain/value_objects/platform.py

Currently, Platform is in signal_chain_enums.py.
This test verifies the expected file structure.
"""

import importlib.util


def test_platform_has_separate_module() -> None:
    """Test that Platform enum exists in its own module file.

    Per T9 scope:
    - libs/core/src/core/domain/value_objects/platform.py

    This file should contain the Platform enum with values from wiki:314-322:
    NAM, IR, AIDA_X, etc.
    """
    # Try to import from the expected location
    spec = importlib.util.find_spec("core.domain.value_objects.platform")

    # This will fail because platform.py doesn't exist
    assert spec is not None, (
        "Platform should be in its own file: "
        "libs/core/src/core/domain/value_objects/platform.py"
    )

    # Verify we can import Platform from it
    import sys
    module = importlib.util.module_from_spec(spec)
    if spec.loader:
        spec.loader.exec_module(module)
    sys.modules["core.domain.value_objects.platform"] = module

    assert hasattr(module, "Platform"), (
        "platform.py should export Platform enum"
    )

    # Verify the enum has expected platform values
    platform_enum = getattr(module, "Platform")
    expected_values = {"NAM", "IR", "AIDA_X"}
    actual_values = {member.name for member in platform_enum}

    # Check that at least these core platforms exist
    assert expected_values.issubset(actual_values), (
        f"Platform should have at least these values: {expected_values}, "
        f"got: {actual_values}"
    )
