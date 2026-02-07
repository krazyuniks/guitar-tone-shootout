"""DITrack ORM model re-export.

This module provides the DITrack model for import consistency.
The actual model definition is in shootout.py to keep related models together.
"""

from webapp.adapters.persistence.models.shootout import DITrack

__all__ = ["DITrack"]
