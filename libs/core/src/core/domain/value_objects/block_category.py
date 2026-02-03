"""Block category enum for signal chain effects.

Defines standard categories based on professional guitar processors
(Line 6 Helix, Fractal Axe-FX, Kemper, Neural DSP, BOSS GT-series).
"""

from enum import Enum


class BlockCategory(str, Enum):
    """Standard block categories with ordering constraints.

    Categories determine where blocks can be placed in the signal chain:
    - PRE_AMP: UTILITY, EQ, DYNAMICS, DISTORTION (before amp)
    - POST_AMP: EQ, DYNAMICS, DELAY, REVERB, MODULATION, SPATIAL, UTILITY
    - AMP: Exactly one required (core of signal chain)
    - IR: Required after AMP type, forbidden after FULL_RIG
    """

    UTILITY = "utility"  # HPF, LPF, Noise Gate, Gain
    EQ = "eq"  # Parametric EQ, Graphic EQ
    DYNAMICS = "dynamics"  # Compressor, Limiter, Gate
    DISTORTION = "distortion"  # Overdrive, Fuzz (effects, not amp modeling)
    MODULATION = "modulation"  # Chorus, Flanger, Phaser, Tremolo
    DELAY = "delay"  # All delay types (analog, digital, tape)
    REVERB = "reverb"  # All reverb types (spring, plate, room, hall)
    SPATIAL = "spatial"  # Stereo widener, Panner
    AMP = "amp"  # NAM amp models
    IR = "ir"  # Impulse responses


# Categories allowed in pre-amp position
PRE_AMP_CATEGORIES: frozenset[BlockCategory] = frozenset(
    {
        BlockCategory.UTILITY,
        BlockCategory.EQ,
        BlockCategory.DYNAMICS,
        BlockCategory.DISTORTION,
    }
)

# Categories allowed in post-amp position
POST_AMP_CATEGORIES: frozenset[BlockCategory] = frozenset(
    {
        BlockCategory.UTILITY,
        BlockCategory.EQ,
        BlockCategory.DYNAMICS,
        BlockCategory.MODULATION,
        BlockCategory.DELAY,
        BlockCategory.REVERB,
        BlockCategory.SPATIAL,
    }
)
