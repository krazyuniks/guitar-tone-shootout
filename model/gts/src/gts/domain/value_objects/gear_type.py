"""GearType enum for categorizing gear items.

Defines the types of gear available in the signal chain system.
"""

from enum import Enum


class GearType(str, Enum):
    """Type of gear represented by a signal chain block.

    Signal chain grammar rules depend on gear type:
    - PEDAL: Pre-amp effect (overdrive, distortion, fuzz, wah, etc.)
    - AMP: Amp head capture, requires IR after
    - FULL_RIG: Full rig capture with baked-in IR, no IR allowed after
    - IR: Impulse response, required after AMP only
    - OUTBOARD: External rack gear (studio outboard, preamps, EQs, etc.)
    """

    PEDAL = "pedal"
    AMP = "amp"
    FULL_RIG = "full_rig"
    IR = "ir"
    OUTBOARD = "outboard"
