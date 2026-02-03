"""Job and Audit ORM models for background processing and event logging."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.domain.value_objects.job_status import JobStatus, JobType  # type: ignore[import-untyped]

from .base import Base, EnumByValue, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .user import User


class Job(UUIDMixin, TimestampMixin, Base):
    """Background processing job model.

    Tracks the lifecycle of a background job from creation through
    completion, with progress updates, error handling, and retry support.

    Supports parent/child job hierarchies for complex workflows where
    a parent job spawns multiple child jobs.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Owner's user ID (None for system-initiated jobs)
        job_type: Type of job (from JobType enum)
        parent_job_id: ID of parent job (None for root jobs)
        status: Current job status (from JobStatus enum)
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

    __tablename__ = "jobs"

    # User relationship
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Job type
    job_type: Mapped[JobType] = mapped_column(
        EnumByValue(JobType),
        nullable=False,
    )

    # Parent/child relationship for job hierarchies
    parent_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Dependencies (stored as JSON array of UUIDs)
    # Note: depends_on is a list of job IDs this job depends on.
    # We store this as JSON since SQLAlchemy doesn't have native array support for SQLite.
    # PostgreSQL would use ARRAY(Uuid) but this works across both.
    depends_on: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Job status
    status: Mapped[JobStatus] = mapped_column(
        EnumByValue(JobStatus),
        nullable=False,
        default=JobStatus.PENDING,
    )

    # Progress tracking
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Retry tracking
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Result and error tracking
    result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Task tracking (for background workers)
    task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Entity reference (what this job is processing)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # Relationships
    user: Mapped[User | None] = relationship(
        "User",
        back_populates="jobs",
        lazy="raise",
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_jobs_user_id", "user_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_entity_id", "entity_id"),
        Index("ix_jobs_task_id", "task_id"),
    )


class AuditLog(Base):
    """Audit log entry for tracking user actions and security events.

    This model uses uuid4 for the primary key (not UUIDv7) because:
    1. Audit logs are append-only (no updates), so time-sorting by PK
       is not needed - we sort by timestamp column instead
    2. Audit logs are rarely looked up by ID individually
    3. The timestamp column with its index handles chronological queries

    JSONB columns are used for changes and extra_data because:
    - changes: Stores before/after diffs with dynamic structure per resource type
    - extra_data: Catch-all for unpredictable auxiliary information

    Attributes:
        id: Unique identifier (uuid4)
        timestamp: When the action occurred
        user_id: The user who performed the action (null for anonymous/system)
        ip_address: Client IP address
        user_agent: Client user agent string
        action: The type of action performed
        resource_type: The type of resource affected
        resource_id: The ID of the specific resource affected
        changes: JSON object containing before/after values for updates
        extra_data: Additional context about the action
        request_id: Correlation ID for the HTTP request
        trace_id: OpenTelemetry trace ID for distributed tracing
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # JSONB columns - see model docstring for justification
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Note: Column name is 'metadata' in database but exposed as 'extra_data' in Python
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_action", "action"),
    )
