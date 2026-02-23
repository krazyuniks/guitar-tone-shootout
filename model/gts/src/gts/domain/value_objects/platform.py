"""Platform enum for signal chain processing targets.

Defines the supported modelling platforms for signal chain processing.
"""

from enum import Enum


class Platform(str, Enum):
    """Target platform for signal chain processing.

    Supports multiple modelling platforms with different characteristics.
    """

    NAM = "nam"  # Neural Amp Modeler
    AIDA_X = "aida_x"  # AIDA-X neural models
    IR = "ir"  # Impulse Response only (cab sim)
    AA_SNAPSHOT = "aa_snapshot"  # Axe-FX/Helix snapshots
    PROTEUS = "proteus"  # Proteus Tone Capture
