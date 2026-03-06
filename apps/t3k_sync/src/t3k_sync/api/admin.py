"""T3K Sync Admin API - endpoints for T3K-specific sync management.

No authentication required. Access is controlled at the network level.
These endpoints query T3K-owned tables and use T3K-internal services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.db import get_core_session
from source_t3k.adapters.outbound.models import SyncCheckpoint
from t3k_sync.api.schemas import (
    APICallWindowMetrics,
    APIStatsResponse,
    SyncCheckpointInfo,
    SyncLagResponse,
    SyncStatsResponse,
    SyncStatusResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from webapp.adapters.persistence.models.job import Job

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Known source names
KNOWN_SOURCES = {"t3k"}


def validate_source(source: str) -> None:
    """Validate source name, raise 404 if unknown."""
    if source not in KNOWN_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")


async def _get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session using messaging's core session."""
    async with get_core_session() as session:
        yield session


@router.get("/sources/{source}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    source: str,
    session: AsyncSession = Depends(_get_db),
) -> SyncStatusResponse:
    """Get sync status for a source."""
    validate_source(source)

    # Check for any running source_sync job
    running_stmt = select(Job).where(
        Job.job_type == JobType.SOURCE_SYNC,
        Job.status == JobStatus.RUNNING,
    )
    running_result = await session.execute(running_stmt)
    running_job = running_result.scalar_one_or_none()
    status = "running" if running_job is not None else "idle"

    # Query tone checkpoint
    tone_stmt = (
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.source_name == source,
            SyncCheckpoint.entity_type.in_(["tone", "tones"]),
        )
        .order_by(SyncCheckpoint.last_synced_at.desc())
        .limit(1)
    )
    tone_result = await session.execute(tone_stmt)
    tone_checkpoint = tone_result.scalar_one_or_none()

    # Query model checkpoint
    model_stmt = (
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.source_name == source,
            SyncCheckpoint.entity_type.in_(["model", "models"]),
        )
        .order_by(SyncCheckpoint.last_synced_at.desc())
        .limit(1)
    )
    model_result = await session.execute(model_stmt)
    model_checkpoint = model_result.scalar_one_or_none()

    checkpoint = None
    if tone_checkpoint or model_checkpoint:
        checkpoint = SyncCheckpointInfo(
            last_tone_id=tone_checkpoint.last_record_id if tone_checkpoint else None,
            last_model_id=model_checkpoint.last_record_id if model_checkpoint else None,
        )

    return SyncStatusResponse(status=status, enabled=True, checkpoint=checkpoint)


@router.get("/sources/{source}/sync/stats", response_model=SyncStatsResponse)
async def get_sync_stats(
    source: str,
    session: AsyncSession = Depends(_get_db),
) -> SyncStatsResponse:
    """Get sync statistics for a source."""
    validate_source(source)

    stmt = select(func.sum(SyncCheckpoint.total_synced)).where(SyncCheckpoint.source_name == source)
    result = await session.execute(stmt)
    total_synced = result.scalar_one_or_none() or 0

    return SyncStatsResponse(total_synced=total_synced, last_sync_duration=None, queue_depths={})


@router.get("/sources/{source}/sync/lag", response_model=SyncLagResponse)
async def get_sync_lag(
    source: str,
    session: AsyncSession = Depends(_get_db),
) -> SyncLagResponse:
    """Get sync lag (time since last successful sync) for a source."""
    validate_source(source)

    stmt = select(func.max(SyncCheckpoint.last_synced_at)).where(
        SyncCheckpoint.source_name == source
    )
    result = await session.execute(stmt)
    last_synced_at = result.scalar_one_or_none()

    if last_synced_at is None:
        return SyncLagResponse(lag_seconds=None)

    now = datetime.now(UTC)
    if last_synced_at.tzinfo is None:
        last_synced_at = last_synced_at.replace(tzinfo=UTC)
    lag = (now - last_synced_at).total_seconds()

    return SyncLagResponse(lag_seconds=lag)


@router.get("/sources/{source}/sync/api-stats", response_model=APIStatsResponse)
async def get_api_stats(source: str) -> APIStatsResponse:
    """Get API call statistics for a source."""
    validate_source(source)

    from source_t3k.services.api_call_tracker import get_tracker

    metrics = get_tracker().get_metrics()
    return APIStatsResponse(
        windows=[
            APICallWindowMetrics(
                window_seconds=m.window_seconds,
                successful=m.successful,
                failed=m.failed,
                avg_success_per_minute=m.avg_success_per_minute,
                avg_failure_per_minute=m.avg_failure_per_minute,
            )
            for m in metrics
        ]
    )


@router.post("/auth/refresh-t3k", response_model=TokenRefreshResponse)
async def refresh_t3k_token(request: TokenRefreshRequest) -> TokenRefreshResponse:
    """Refresh T3K OAuth access token using the stored refresh token."""
    from source_t3k.adapters.inbound.exceptions import T3KAPIError
    from source_t3k.adapters.inbound.token_manager import T3KTokenManager

    token_manager = T3KTokenManager(
        auth_file_path=request.auth_file_path,
        base_url=request.base_url,
        encryption_key=request.encryption_key,
    )
    try:
        await token_manager.get_access_token()
        return TokenRefreshResponse(auth_status="valid", message="Token refreshed successfully")
    except T3KAPIError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "re-authenticate" in error_msg.lower():
            return TokenRefreshResponse(
                auth_status="login_required",
                message="Refresh token expired — run `just t3k-login`",
            )
        return TokenRefreshResponse(
            auth_status="refresh_failed",
            message=f"Token refresh failed: {error_msg}",
        )
    except Exception as e:
        return TokenRefreshResponse(
            auth_status="refresh_failed",
            message=f"Unexpected error during token refresh: {e}",
        )
    finally:
        await token_manager.close()
