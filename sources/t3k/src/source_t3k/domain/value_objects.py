"""T3K-specific value objects.

These enums represent T3K-specific platform types and pack classifications.
They are NOT part of the core domain - they represent data as it exists
in the Tone3000 system before transformation to GTS format.
"""

from enum import Enum


class T3KPlatform(str, Enum):
    """Platform type in the T3K system.

    T3K uses these platforms to categorise their model packs.
    These are mapped to core Platform enum during synchronisation.
    """

    NAM = "nam"
    AIDA_X = "aida_x"
    IR = "ir"


class T3KGearKind(str, Enum):
    """Gear kind classification in the T3K system.

    Categorises tones by the type of gear they model.
    """

    AMP = "amp"
    PEDAL = "pedal"
    IR = "ir"


class T3KPackType(str, Enum):
    """Pack type classification in the T3K system.

    T3K uses these types to categorise packs by gear type.
    These are mapped to core GearType during synchronisation.
    """

    AMP = "amp"
    PEDAL = "pedal"
    IR = "ir"
