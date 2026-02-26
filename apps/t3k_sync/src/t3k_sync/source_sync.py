"""Source sync runner extracted from the monolithic worker."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text

from gts.domain.auth_gate import check_auth_status
from gts.domain.value_objects.job_status import JobStatus, JobType
from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import SyncMode
from source_t3k.services.model_downloader import ModelDownloader
from source_t3k.services.sync_service import T3KSyncService
from webapp.adapters.persistence.models.job import Job
from worker.db import get_core_session, get_core_session_no_tx

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
            msg += " - run `just t3k-login`"
        raise RuntimeError(msg)


def _build_api_client() -> tuple[T3KTokenManager, T3KAPIClient]:
    """Build T3K token manager + API client from environment configuration."""
    base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")
    auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    encryption_key = os.environ["OAUTH_ENCRYPTION_KEY"]
    token_manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    api_client = T3KAPIClient(
        token_manager=token_manager, base_url=base_url, requests_per_second=1.0
    )
    return token_manager, api_client


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
            max_attempts=3,
        )
        session.add(job)
        await session.flush()
        return job.id


async def _update_job_status(job_id: UUID, status: JobStatus, **fields: object) -> None:
    """Update job status in gts_core."""
    async with get_core_session() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is not None:
            job.status = status
            for key, value in fields.items():
                setattr(job, key, value)


async def run_source_sync(job_id: UUID | None = None) -> UUID:
    """Run one source sync batch (one-shot, lock-protected)."""
    tracked_job_id = job_id if job_id is not None else await _create_source_sync_job()

    try:
        _check_auth_gate()
    except RuntimeError as error:
        await _update_job_status(
            tracked_job_id,
            JobStatus.FAILED,
            error=str(error),
            completed_at=datetime.now(UTC),
        )
        raise

    token_manager: T3KTokenManager | None = None
    async with get_core_session_no_tx() as lock_session:
        result = await lock_session.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
        )
        acquired = result.scalar()
        if not acquired:
            logger.info("Sync lock already held, skipping run")
            await _update_job_status(
                tracked_job_id,
                JobStatus.COMPLETED,
                message="Superseded by an active sync run",
                completed_at=datetime.now(UTC),
            )
            return tracked_job_id

        now = datetime.now(UTC)
        await _update_job_status(
            tracked_job_id, JobStatus.RUNNING, started_at=now, last_heartbeat=now
        )

        try:
            async with get_core_session_no_tx() as session:
                token_manager, api_client = _build_api_client()
                model_downloader = _build_model_downloader(api_client)
                publisher = GearSyncPublisher(session=session, queue_name="source_events")
                sync_service = T3KSyncService(
                    api_client=api_client,
                    session=session,
                    model_downloader=model_downloader,
                )

                async def renew_lock() -> None:
                    await _update_job_status(
                        tracked_job_id,
                        JobStatus.RUNNING,
                        last_heartbeat=datetime.now(UTC),
                    )

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

            await _update_job_status(
                tracked_job_id,
                JobStatus.COMPLETED,
                completed_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception("Sync batch failed")
            await _update_job_status(
                tracked_job_id,
                JobStatus.FAILED,
                error="Sync batch failed",
                completed_at=datetime.now(UTC),
            )
        finally:
            if token_manager is not None:
                await token_manager.close()

            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
            )

    return tracked_job_id
