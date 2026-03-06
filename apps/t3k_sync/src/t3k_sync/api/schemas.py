"""Pydantic schemas for T3K sync admin API endpoints."""

from pydantic import BaseModel, Field


class SyncCheckpointInfo(BaseModel):
    """Checkpoint information for sync status."""

    last_tone_id: str | None = None
    last_model_id: str | None = None


class SyncStatusResponse(BaseModel):
    """Response for sync status endpoint."""

    status: str  # "running" or "idle"
    enabled: bool
    checkpoint: SyncCheckpointInfo | None = None


class SyncStatsResponse(BaseModel):
    """Response for sync stats endpoint."""

    total_synced: int
    last_sync_duration: float | None = None
    queue_depths: dict[str, int] = Field(default_factory=dict)


class SyncLagResponse(BaseModel):
    """Response for sync lag endpoint."""

    lag_seconds: float | None = None


class APICallWindowMetrics(BaseModel):
    """Metrics for a single time window."""

    window_seconds: int
    successful: int
    failed: int
    avg_success_per_minute: float
    avg_failure_per_minute: float


class APIStatsResponse(BaseModel):
    """Response for API stats endpoint."""

    windows: list[APICallWindowMetrics]


class TokenRefreshRequest(BaseModel):
    """Request to refresh T3K OAuth token."""

    auth_file_path: str
    base_url: str
    encryption_key: str


class TokenRefreshResponse(BaseModel):
    """Response from token refresh endpoint."""

    auth_status: str
    message: str
