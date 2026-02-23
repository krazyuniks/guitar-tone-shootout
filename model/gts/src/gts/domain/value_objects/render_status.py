"""Render status value object for video composition jobs.

Tracks the status of video rendering jobs with support for state transitions.
"""

from dataclasses import dataclass
from enum import Enum


class RenderStatusEnum(str, Enum):
    """Enumeration of render job statuses."""

    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETE = "complete"
    FAILED = "failed"

    @classmethod
    def terminal_states(cls) -> set["RenderStatusEnum"]:
        """Return the set of terminal states.

        Terminal states are final states that cannot transition further.

        Returns:
            Set containing COMPLETE and FAILED states
        """
        return {cls.COMPLETE, cls.FAILED}

    @classmethod
    def active_states(cls) -> set["RenderStatusEnum"]:
        """Return the set of active (non-terminal) states.

        Active states are transient states that will eventually transition.

        Returns:
            Set containing PENDING and RENDERING states
        """
        return {cls.PENDING, cls.RENDERING}

    def is_terminal(self) -> bool:
        """Check if this status is terminal.

        Returns:
            True if status is COMPLETE or FAILED
        """
        return self in self.terminal_states()

    def is_active(self) -> bool:
        """Check if this status is active (non-terminal).

        Returns:
            True if status is PENDING or RENDERING
        """
        return self in self.active_states()

    def can_transition_to(self, target: "RenderStatusEnum") -> bool:
        """Check if transition to target state is valid.

        Valid transitions:
        - PENDING -> RENDERING
        - PENDING -> FAILED (job rejected before starting)
        - RENDERING -> COMPLETE
        - RENDERING -> FAILED

        Terminal states (COMPLETE, FAILED) cannot transition.

        Args:
            target: Target state to transition to

        Returns:
            True if transition is valid
        """
        valid_transitions = {
            self.PENDING: {self.RENDERING, self.FAILED},
            self.RENDERING: {self.COMPLETE, self.FAILED},
            self.COMPLETE: set(),
            self.FAILED: set(),
        }

        return target in valid_transitions.get(self, set())


@dataclass(frozen=True)
class RenderStatus:
    """Status of a video rendering job.

    Immutable value object representing the current state of a render job.
    """

    job_id: str
    status: str
    output_path: str | None = None
    error_message: str | None = None
    progress: float | None = None
