"""Composition specification value object for video rendering.

Generic specification for video composition jobs, decoupled from specific
composition types like shootouts.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompositionSpec:
    """Specification for a video composition.

    Immutable value object that encapsulates all the data needed to render
    a video composition. The composition_type field indicates the renderer
    to use, while the data field contains type-specific parameters.
    """

    composition_type: str
    data: dict[str, Any]
