"""Source sync runner extracted from the monolithic worker."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text

from gts.domain.auth_gate import check_auth_status
from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.db import get_core_session, get_core_session_no_tx
from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import SyncMode
from source_t3k.services.model_downloader import ModelDownloader
from source_t3k.services.sync_service import T3KSyncService
from webapp.adapters.persistence.models.job import Job

if TYPE_CHECKING:
    from t3k_sync.health import SyncHealthTracker

logger = logging.getLogger(__name__)

SYNC_SOURCE = "t3k"
_PG_ADVISORY_LOCK_KEY = 7356951


def _check_auth_gate(auth_file_path: str | None = None) -> None:
    """Check auth status before making any T3K API calls."""
    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    status = check_auth_status(auth_file_path)
    if not status.can_proceed():
        msg = f"T3K auth status is {status.value}"
        if status.needs_login():
            msg += " - run `just t3k-auth`"
        raise RuntimeError(msg)


def build_token_manager() -> T3KTokenManager:
    """Build T3K token manager from environment configuration."""
    base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")
    auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    encryption_key = os.environ["OAUTH_ENCRYPTION_KEY"]
    return T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )


def _build_api_client(token_manager: T3KTokenManager) -> T3KAPIClient:
    """Build T3K API client with the given token manager."""
    base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")
    return T3KAPIClient(token_manager=token_manager, base_url=base_url, requests_per_second=1.0)


def _build_model_downloader(api_client: T3KAPIClient) -> ModelDownloader:
    """Build model downloader rooted under the processed volume."""
    base_path = Path(os.environ["GTS_STORAGE_ROOT"]) / "source_downloads" / "t3k"
    return ModelDownloader(
        base_path=base_path,
        http_client=api_client._client,
        get_auth_headers=api_client._get_auth_headers,
        rate_limiter=api_client._rate_limiter,
    )


def _get_sync_mode() -> SyncMode:
    """Read sync mode from T3K_SYNC_MODE env var."""
    raw = os.getenv("T3K_SYNC_MODE", "bau").lower()
    if raw == "catch_up":
        return SyncMode.CATCH_UP
    return SyncMode.BAU


async def _create_source_sync_job() -> UUID:
    """Create a SOURCE_SYNC job row for scheduler-triggered runs."""
    async with get_core_session() as session:
        job = Job(
            id=uuid4(),
            user_id=None,
            job_type=JobType.SOURCE_SYNC,
            status=JobStatus.PENDING,
            progress=0,
            attempt=1,
            max_attempts=2,
        )
        session.add(job)
        await session.flush()
        return job.id


async def _update_job_status(
    job_id: UUID,
    status: JobStatus,
    *,
    message: str | None = None,
    error: str | None = None,
    renewal: bool = False,
) -> None:
    """Route the SOURCE_SYNC job lifecycle through the transition service.

    Timestamps (started_at, last_heartbeat, completed_at) are the service's
    bookkeeping; RUNNING -> RUNNING renewals are the lease heartbeat.
    """
    from webapp.services.job_transitions import TransitionError, transition_job

    async with get_core_session_no_tx() as session:
        try:
            await transition_job(
                session, job_id, status, message=message, error=error, renewal=renewal
            )
        except TransitionError as exc:
            logger.warning("Sync job %s transition rejected: %s", job_id, exc)


async def run_source_sync(
    job_id: UUID | None = None,
    *,
    tracker: SyncHealthTracker | None = None,
    token_manager: T3KTokenManager | None = None,
) -> UUID:
    """Run one source sync batch (one-shot, lock-protected)."""
    tracked_job_id = job_id if job_id is not None else await _create_source_sync_job()

    try:
        _check_auth_gate()
    except RuntimeError as error:
        await _update_job_status(tracked_job_id, JobStatus.FAILED, error=str(error))
        raise

    _owns_tm = token_manager is None
    effective_tm = token_manager
    async with get_core_session_no_tx() as lock_session:
        result = await lock_session.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
        )
        acquired = result.scalar()
        if not acquired:
            logger.info("Sync lock already held, skipping run")
            # A superseded run never did any work: CANCELLED, not COMPLETED
            # (PENDING -> COMPLETED is not a transition-table edge).
            await _update_job_status(
                tracked_job_id,
                JobStatus.CANCELLED,
                message="Superseded by an active sync run",
            )
            return tracked_job_id

        await _update_job_status(tracked_job_id, JobStatus.RUNNING)

        try:
            async with get_core_session_no_tx() as session:
                if effective_tm is None:
                    effective_tm = build_token_manager()
                api_client = _build_api_client(effective_tm)
                model_downloader = _build_model_downloader(api_client)
                publisher = GearSyncPublisher(session=session, queue_name="source_events")
                sync_service = T3KSyncService(
                    api_client=api_client,
                    session=session,
                    model_downloader=model_downloader,
                )

                async def renew_lock() -> None:
                    # RUNNING -> RUNNING lease heartbeat renewal by the holder.
                    await _update_job_status(tracked_job_id, JobStatus.RUNNING, renewal=True)

                mode = _get_sync_mode()
                result = await sync_service.run_sync_batch(
                    publisher, mode=mode, on_progress=renew_lock
                )

                logger.info(
                    "Sync batch complete: mode=%s tones=%d skipped=%d models=%d files=%d api_calls=%d hit_known=%s",
                    result.mode.value,
                    result.tones_processed,
                    result.tones_skipped,
                    result.models_staged,
                    result.files_downloaded,
                    result.api_calls_made,
                    result.hit_known_tone,
                )

            await _update_job_status(tracked_job_id, JobStatus.COMPLETED)
            if tracker is not None:
                tracker.record_sync_success()
        except Exception:
            logger.exception("Sync batch failed")
            await _update_job_status(tracked_job_id, JobStatus.FAILED, error="Sync batch failed")
            if tracker is not None:
                tracker.record_sync_failure("Sync batch failed")
        finally:
            if _owns_tm and effective_tm is not None:
                await effective_tm.close()

            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
            )

    return tracked_job_id
