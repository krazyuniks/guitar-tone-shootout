"""Job status value object for domain layer."""

from enum import Enum


class JobStatus(str, Enum):
    """Status of a background processing job.

    This is a value object representing the possible states
    of a job in the processing lifecycle.

    State transitions:
        PENDING -> QUEUED -> RUNNING -> COMPLETED
                                    -> FAILED
                         -> CANCELLED
        QUEUED -> CANCELLED
        PENDING -> CANCELLED
    """

    PENDING = "pending"  # Job created, not yet queued
    QUEUED = "queued"  # Job sent to worker queue
    RUNNING = "running"  # Worker is processing
    COMPLETED = "completed"  # Job finished successfully
    FAILED = "failed"  # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled by user
    DEAD_LETTERED = "dead_lettered"  # Job exceeded max retry attempts

    @classmethod
    def terminal_states(cls) -> frozenset["JobStatus"]:
        """Return the set of terminal (final) states."""
        return frozenset({cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.DEAD_LETTERED})

    @classmethod
    def active_states(cls) -> frozenset["JobStatus"]:
        """Return the set of active (non-terminal) states."""
        return frozenset({cls.PENDING, cls.QUEUED, cls.RUNNING})

    def is_terminal(self) -> bool:
        """Check if this status is a terminal state."""
        return self in self.terminal_states()

    def is_active(self) -> bool:
        """Check if this status is an active state."""
        return self in self.active_states()

    def can_transition_to(self, target: "JobStatus") -> bool:
        """Check if a transition to the target status is valid.

        Args:
            target: The status to transition to

        Returns:
            True if the transition is valid, False otherwise
        """
        valid_transitions: dict[JobStatus, frozenset[JobStatus]] = {
            JobStatus.PENDING: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
            JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
            JobStatus.RUNNING: frozenset(
                {
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                    JobStatus.DEAD_LETTERED,
                }
            ),
            # FAILED can retry back to PENDING (for retryable failures)
            JobStatus.FAILED: frozenset({JobStatus.PENDING, JobStatus.DEAD_LETTERED}),
            JobStatus.COMPLETED: frozenset(),
            JobStatus.CANCELLED: frozenset(),
            # Admin can retry dead-lettered jobs
            JobStatus.DEAD_LETTERED: frozenset({JobStatus.PENDING}),
        }
        return target in valid_transitions.get(self, frozenset())


class JobType(str, Enum):
    """Type of background job.

    Categorises jobs by their purpose for routing and prioritisation.
    """

    AUDIO_PROCESSING = "audio_processing"  # Process DI track through signal chain
    VIDEO_COMPOSITION = "video_composition"  # Compose shootout video
    GEAR_SYNC = "gear_sync"  # Sync gear from source
    MODEL_DOWNLOAD = "model_download"  # Download NAM model file
    IR_DOWNLOAD = "ir_download"  # Download IR file
    NOTIFICATION = "notification"  # Send user notification
