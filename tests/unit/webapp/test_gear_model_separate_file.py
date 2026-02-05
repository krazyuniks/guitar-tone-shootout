"""Tests that GearModel should exist in its own file.

Per task T9 acceptance criteria, GearModel should be in:
  apps/webapp/src/webapp/adapters/persistence/models/gear_model.py

Currently, GearModel is in gear.py alongside Gear.
This test verifies the expected file structure.
"""

import importlib.util


def test_gear_model_has_separate_module() -> None:
    """Test that GearModel exists in its own module file.

    Per T9 scope:
    - apps/webapp/src/webapp/adapters/persistence/models/gear_model.py

    This file should contain the GearModel ORM class.
    """
    # Try to import from the expected location
    spec = importlib.util.find_spec("webapp.adapters.persistence.models.gear_model")

    # This will fail because gear_model.py doesn't exist
    assert spec is not None, (
        "GearModel should be in its own file: "
        "apps/webapp/src/webapp/adapters/persistence/models/gear_model.py"
    )

    # Verify we can import GearModel from it
    module = importlib.util.module_from_spec(spec)
    assert hasattr(module, "GearModel"), (
        "gear_model.py should export GearModel class"
    )
