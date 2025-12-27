"""Job model for tracking background processing jobs."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.shootout import Shootout
    from app.models.user import User


class JobStatus(str, Enum):
    """Status of a background processing job."""

    PENDING = "pending"  # Job created, not yet queued
    QUEUED = "queued"  # Job sent to worker queue
    RUNNING = "running"  # Worker is processing
    COMPLETED = "completed"  # Job finished successfully
    FAILED = "failed"  # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled by user


class Job(Base, UUIDMixin, TimestampMixin):
    """Background processing job for shootout generation.

    Tracks the lifecycle of a shootout processing job from submission
    through completion, with progress updates and error handling.
    """

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_status", "user_id", "status"),)

    # Owner of the job
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Job status and progress
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status"),
        default=JobStatus.PENDING,
        index=True,
    )
    progress: Mapped[int] = mapped_column(default=0)
    message: Mapped[str | None] = mapped_column(String(500))

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Results
    result_path: Mapped[str | None] = mapped_column(String(1000))
    error: Mapped[str | None] = mapped_column(Text)

    # TaskIQ task ID for tracking/cancellation
    task_id: Mapped[str | None] = mapped_column(String(100))

    # Job configuration (stored as JSON-compatible dict)
    # Kept for backwards compatibility, but prefer using Shootout model
    config: Mapped[str | None] = mapped_column(Text)

    # Optional link to Shootout (replaces config when present)
    shootout_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("shootouts.id", ondelete="SET NULL"),
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="jobs")
    shootout: Mapped["Shootout | None"] = relationship(back_populates="jobs")

    def __repr__(self) -> str:
        """Return string representation of the job."""
        return f"<Job {self.id} status={self.status.value} progress={self.progress}%>"
