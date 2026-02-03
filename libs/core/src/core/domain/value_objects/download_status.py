"""Download status enum for model file downloads.

Tracks the lifecycle of a model file download from pending through
completion or failure.
"""

from enum import Enum


class DownloadStatus(str, Enum):
    """Status of a model file download.

    States:
    - PENDING: Download not yet started
    - QUEUED: Download job queued for processing
    - DOWNLOADING: Currently downloading the file
    - COMPLETED: Download successful, file available locally
    - FAILED: Download failed (may be retried)
    """

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """Check if this is a terminal (final) status.

        Terminal statuses are COMPLETED and FAILED.
        """
        return self in (DownloadStatus.COMPLETED, DownloadStatus.FAILED)

    def is_active(self) -> bool:
        """Check if download is currently in progress.

        Active statuses are QUEUED and DOWNLOADING.
        """
        return self in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)

    def can_retry(self) -> bool:
        """Check if download can be retried from this status.

        Only FAILED status can be retried.
        """
        return self == DownloadStatus.FAILED
