"""Job entity for domain layer."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from gts.domain.entities.base import Entity, new_id, utcnow
from gts.domain.value_objects.job_status import JobStatus, JobType


class JobError(Exception):
    """Base exception for Job domain errors."""

    pass


class InvalidStateTransitionError(JobError):
    """Raised when an invalid state transition is attempted."""

    pass


class DependencyNotCompletedError(JobError):
    """Raised when trying to run a job whose dependencies are not complete."""

    pass


@dataclass(eq=False, slots=True)
class Job(Entity):
    """Entity representing a background processing job.

    Jobs track the lifecycle of processing from creation
    through completion, with state machine validation for transitions.

    Supports job groups where a parent job has child jobs.
    Child jobs can specify dependencies via depends_on,
    and will only run when all dependencies are complete.

    Attributes:
        id: Unique identifier
        user_id: Owner's user ID (None for system-initiated jobs)
        job_type: Type of job
        parent_job_id: ID of parent job for job groups (None for root jobs)
        depends_on: List of job IDs this job depends on
        status: Current job status
        progress: Progress percentage (0-100)
        message: Status message for display
        started_at: When processing started
        completed_at: When processing completed
        last_heartbeat: Last heartbeat timestamp from worker
        attempt: Current retry attempt (1-indexed)
        max_attempts: Maximum number of retry attempts
        next_retry_at: When the next retry should be attempted
        result_path: Path to result file (after completion)
        error: Error message (if failed)
        task_id: TaskIQ task ID for tracking
        entity_id: ID of the entity this job processes (shootout, gear, etc.)
        created_at: When the job was created
        updated_at: When the job was last updated
    """

    user_id: UUID | None = None  # None for system-initiated jobs
    job_type: JobType = JobType.AUDIO_PROCESSING
    parent_job_id: UUID | None = None
    depends_on: list[UUID] = field(default_factory=list)
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_heartbeat: datetime | None = None
    attempt: int = 1
    max_attempts: int = 3
    next_retry_at: datetime | None = None
    result_path: str | None = None
    error: str | None = None
    task_id: str | None = None
    entity_id: UUID | None = None
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def _transition_to(self, new_status: JobStatus) -> None:
        """Validate and execute a status transition.

        Args:
            new_status: The status to transition to

        Raises:
            InvalidStateTransitionError: If the transition is not valid
        """
        if not self.status.can_transition_to(new_status):
            raise InvalidStateTransitionError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status
        self.updated_at = utcnow()

    def queue(self, task_id: str) -> None:
        """Mark the job as queued.

        Args:
            task_id: The TaskIQ task ID

        Raises:
            InvalidStateTransitionError: If not in PENDING state
        """
        self._transition_to(JobStatus.QUEUED)
        self.task_id = task_id

    def start(self) -> None:
        """Mark the job as running.

        Raises:
            InvalidStateTransitionError: If not in QUEUED state
        """
        self._transition_to(JobStatus.RUNNING)
        self.started_at = utcnow()
        self.progress = 0

    def update_progress(self, progress: int, message: str | None = None) -> None:
        """Update job progress.

        Args:
            progress: Progress percentage (0-100)
            message: Optional status message

        Raises:
            ValueError: If progress is not in valid range
            JobError: If job is not in RUNNING state
        """
        if not 0 <= progress <= 100:
            raise ValueError(f"Progress must be between 0 and 100, got {progress}")

        if self.status != JobStatus.RUNNING:
            raise JobError(f"Cannot update progress on job in {self.status.value} state")

        self.progress = progress
        if message is not None:
            self.message = message
        self.updated_at = utcnow()

    def complete(self, result_path: str) -> None:
        """Mark the job as completed successfully.

        Args:
            result_path: Path to the result file

        Raises:
            InvalidStateTransitionError: If not in RUNNING state
        """
        self._transition_to(JobStatus.COMPLETED)
        self.progress = 100
        self.result_path = result_path
        self.completed_at = utcnow()

    def fail(self, error: str) -> None:
        """Mark the job as failed.

        Args:
            error: Error message describing the failure

        Raises:
            InvalidStateTransitionError: If not in RUNNING state
        """
        self._transition_to(JobStatus.FAILED)
        self.error = error
        self.completed_at = utcnow()

    def cancel(self) -> None:
        """Cancel the job.

        Raises:
            InvalidStateTransitionError: If already in a terminal state
        """
        self._transition_to(JobStatus.CANCELLED)
        self.completed_at = utcnow()

    def update_heartbeat(self) -> None:
        """Update the heartbeat timestamp.

        Called by workers to indicate they are still processing.

        Raises:
            JobError: If job is not in RUNNING state
        """
        if self.status != JobStatus.RUNNING:
            raise JobError(f"Cannot update heartbeat on job in {self.status.value} state")

        self.last_heartbeat = utcnow()
        self.updated_at = utcnow()

    def schedule_retry(self, next_retry_at: datetime) -> None:
        """Schedule a retry for the job.

        Increments the attempt counter and sets the next retry time.
        Transitions from FAILED to PENDING.

        Args:
            next_retry_at: When the next retry should be attempted

        Raises:
            InvalidStateTransitionError: If not in FAILED state
            JobError: If max attempts already reached
        """
        if self.attempt >= self.max_attempts:
            raise JobError(f"Cannot retry job: max attempts ({self.max_attempts}) reached")

        self.attempt += 1
        self.next_retry_at = next_retry_at
        self._transition_to(JobStatus.PENDING)
        # Clear previous run state
        self.completed_at = None
        self.started_at = None
        self.last_heartbeat = None
        self.progress = 0
        self.task_id = None

    def dead_letter(self, error: str) -> None:
        """Move the job to dead letter queue.

        Called when all retry attempts have been exhausted.

        Args:
            error: Final error message

        Raises:
            InvalidStateTransitionError: If not in FAILED or RUNNING state
        """
        self._transition_to(JobStatus.DEAD_LETTERED)
        self.error = error
        self.completed_at = utcnow()

    def reset_for_retry(self) -> None:
        """Reset the job for a manual retry (admin action).

        Resets the job to initial state for retrying from dead-lettered status.

        Raises:
            InvalidStateTransitionError: If not in DEAD_LETTERED state
        """
        self._transition_to(JobStatus.PENDING)
        self.attempt = 1
        self.next_retry_at = None
        self.completed_at = None
        self.started_at = None
        self.last_heartbeat = None
        self.progress = 0
        self.task_id = None
        self.error = None
        self.result_path = None

    @property
    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return self.attempt < self.max_attempts

    @property
    def is_terminal(self) -> bool:
        """Check if the job is in a terminal state."""
        return self.status.is_terminal()

    @property
    def is_active(self) -> bool:
        """Check if the job is in an active state."""
        return self.status.is_active()

    @property
    def duration_seconds(self) -> float | None:
        """Get the duration of the job in seconds.

        Returns:
            Duration in seconds if both started_at and completed_at are set,
            None otherwise.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()
