"""Background jobs package.

This module intentionally avoids eager imports to prevent circular-import
issues with ``worker.main`` during broker bootstrap.
"""

__all__ = [
    "audio",
    "audio_processing",
    "master_audio",
    "shootout",
    "source_sync",
]
