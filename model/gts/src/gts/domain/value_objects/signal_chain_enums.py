"""Signal chain domain enums for value objects.

These enums define the valid values for signal chain composition:
- Platform: Target platform (NAM, AIDA-X, IR, AA_SNAPSHOT, PROTEUS)
- GearType: Type of gear in the signal chain
- EffectCategory: Category of effect for placement rules
- ModelSize: NAM model size variants
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


class GearType(str, Enum):
    """Type of gear represented by a signal chain block.

    Signal chain grammar rules depend on gear type:
    - PEDAL: Pre-amp effect (overdrive, distortion, fuzz, wah, etc.)
    - AMP: Amp head capture, requires IR after
    - FULL_RIG: Full rig capture with baked-in IR, no IR allowed after
    - IR: Impulse response, required after AMP only
    - POST_EFFECT: Post-amp effect (delay, reverb, chorus, etc.)
    - OUTBOARD: External rack gear (studio outboard, preamps, EQs, etc.)
    """

    PEDAL = "pedal"
    AMP = "amp"
    FULL_RIG = "full_rig"
    IR = "ir"
    POST_EFFECT = "post_effect"
    OUTBOARD = "outboard"


class EffectCategory(str, Enum):
    """Category of effect for determining valid placement positions.

    Effect placement rules:
    - PRE_ONLY: Before amp only (overdrive, distortion, fuzz, wah, compressor)
    - POST_ONLY: After amp/cab only (delay, reverb)
    - PRE_OR_POST: Either before or after amp (EQ, modulation, noise gate)
    """

    PRE_ONLY = "pre_only"
    POST_ONLY = "post_only"
    PRE_OR_POST = "pre_or_post"


# Mapping of effect tags/types to their category
# Used by guidance to determine valid positions for effects
EFFECT_PLACEMENT_RULES: dict[str, EffectCategory] = {
    # Pre-amp only effects (gain-based)
    "overdrive": EffectCategory.PRE_ONLY,
    "distortion": EffectCategory.PRE_ONLY,
    "fuzz": EffectCategory.PRE_ONLY,
    "wah": EffectCategory.PRE_ONLY,
    "compressor": EffectCategory.PRE_ONLY,
    "boost": EffectCategory.PRE_ONLY,
    "preamp": EffectCategory.PRE_ONLY,
    # Post-amp only effects (time/ambient-based)
    "delay": EffectCategory.POST_ONLY,
    "reverb": EffectCategory.POST_ONLY,
    # Effects that can go either place
    "eq": EffectCategory.PRE_OR_POST,
    "equalizer": EffectCategory.PRE_OR_POST,
    "chorus": EffectCategory.PRE_OR_POST,
    "flanger": EffectCategory.PRE_OR_POST,
    "phaser": EffectCategory.PRE_OR_POST,
    "tremolo": EffectCategory.PRE_OR_POST,
    "vibrato": EffectCategory.PRE_OR_POST,
    "noise gate": EffectCategory.PRE_OR_POST,
    "noise_gate": EffectCategory.PRE_OR_POST,
    "noisegate": EffectCategory.PRE_OR_POST,
    "gate": EffectCategory.PRE_OR_POST,
    "modulation": EffectCategory.PRE_OR_POST,
}


def get_effect_category(effect_tags: list[str]) -> EffectCategory:
    """Determine the effect category from tags.

    Args:
        effect_tags: List of tag names from the effect/pedal

    Returns:
        The effect category for placement rules.
        Defaults to PRE_OR_POST if no matching tags found.
    """
    for tag in effect_tags:
        tag_lower = tag.lower()
        if tag_lower in EFFECT_PLACEMENT_RULES:
            return EFFECT_PLACEMENT_RULES[tag_lower]
    # Default to pre_or_post if no specific rule matches
    return EffectCategory.PRE_OR_POST


class ModelSize(str, Enum):
    """NAM model size variants.

    Different sizes trade off between accuracy and CPU usage:
    - STANDARD: Full accuracy, highest CPU
    - LITE: Good accuracy, moderate CPU
    - FEATHER: Reduced accuracy, lower CPU
    - NANO: Minimal accuracy, lowest CPU
    """

    STANDARD = "standard"
    LITE = "lite"
    FEATHER = "feather"
    NANO = "nano"
