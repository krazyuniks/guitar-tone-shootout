"""BlockPosition value object for signal chain blocks.

Defines the position of a block in relation to the amp:
- PRE: Before the amp (pre-amp section)
- LOOP: Effects loop (between preamp and power amp)
- POST: After the amp (post-amp section)
"""

from enum import Enum


class BlockPosition(str, Enum):
    """Position of a block in the signal chain relative to the amp.

    Used to track whether a block is in the pre-amp, effects loop,
    or post-amp section of the signal chain.
    """

    PRE = "pre"
    LOOP = "loop"
    POST = "post"
