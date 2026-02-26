"""Scheduled background tasks for the t3k-sync container."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from gts.domain.auth_gate import check_auth_status
from gts.domain.value_objects.job_status import JobStatus
from gts.domain.value_objects.source_auth_status import SourceAuthStatus
from worker.db import get_core_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_REFRESH_WINDOW_SECONDS = 600
_FALLBACK_REFRESH_SECONDS = 1800
_BACKUPS_DIR = Path("/app/backups")

# Test hook: set by tests to inject the test session into DB tasks.
# Allows task functions to share the test's SAVEPOINT-isolated session.
_test_session: AsyncSession | None = None


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def _update_auth_status(auth_file_path: str, status: SourceAuthStatus) -> None:
    """Update auth_status field in auth file. Best-effort."""
    path = Path(auth_file_path)
    try:
        with open(path) as fh:
            data = json.load(fh)
        data["auth_status"] = status.value
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
    except (json.JSONDecodeError, OSError):
        pass


async def refresh_t3k_token(
    auth_file_path: str | None = None,
    encryption_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Check T3K token expiry and refresh if needed."""
    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    if encryption_key is None:
        encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if base_url is None:
        base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")

    path = Path(auth_file_path)
    if not path.exists():
        logger.debug("Auth file not found: %s", auth_file_path)
        return

    status = check_auth_status(auth_file_path)
    if status == SourceAuthStatus.LOGIN_REQUIRED:
        logger.debug("Auth login_required — skipping refresh (run `just t3k-login`)")
        return

    try:
        with open(path) as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return

    expires_at_str = data.get("expires_at")
    saved_at_str = data.get("saved_at")
    now = datetime.now(UTC)
    needs_refresh = False

    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        seconds_until_expiry = (expires_at - now).total_seconds()
        if seconds_until_expiry > _REFRESH_WINDOW_SECONDS:
            if status != SourceAuthStatus.VALID:
                _update_auth_status(auth_file_path, SourceAuthStatus.VALID)
            return
        logger.info(
            "Token expires in %.0f seconds (within %d-second window)",
            seconds_until_expiry,
            _REFRESH_WINDOW_SECONDS,
        )
        needs_refresh = True
    elif saved_at_str:
        saved_at = datetime.fromisoformat(saved_at_str)
        if saved_at.tzinfo is None:
            saved_at = saved_at.replace(tzinfo=UTC)
        age = (now - saved_at).total_seconds()
        if age < _FALLBACK_REFRESH_SECONDS:
            return
        logger.info("No expires_at, last saved %.0f seconds ago — refreshing", age)
        needs_refresh = True
    else:
        logger.warning("Auth file has no expires_at or saved_at — skipping")
        return

    if not needs_refresh:
        return

    if not encryption_key:
        logger.error("OAUTH_ENCRYPTION_KEY not set — cannot refresh")
        return

    _update_auth_status(auth_file_path, SourceAuthStatus.EXPIRING_SOON)

    worker_url = os.getenv("WORKER_ADMIN_URL", "http://worker:8001")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{worker_url}/api/admin/auth/refresh-t3k",
                json={
                    "auth_file_path": auth_file_path,
                    "base_url": base_url,
                    "encryption_key": encryption_key,
                },
            )
            response.raise_for_status()
            result = response.json()
            new_status_str = result.get("auth_status", "refresh_failed")
            try:
                new_status = SourceAuthStatus(new_status_str)
            except ValueError:
                new_status = SourceAuthStatus.REFRESH_FAILED
            _update_auth_status(auth_file_path, new_status)
            if new_status == SourceAuthStatus.VALID:
                logger.info("T3K token refreshed successfully")
            elif new_status == SourceAuthStatus.LOGIN_REQUIRED:
                logger.error("T3K refresh token expired — run `just t3k-login`")
            else:
                logger.warning("T3K token refresh failed — status: %s", new_status_str)
    except httpx.HTTPStatusError as error:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.error("Worker returned error during T3K token refresh: %s", error)
    except httpx.RequestError as error:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.error("Worker unreachable during T3K token refresh: %s", error)
    except Exception:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.exception("Unexpected error during T3K token refresh")


# ---------------------------------------------------------------------------
# Job monitoring
# ---------------------------------------------------------------------------


async def monitor_stale_jobs() -> None:
    """Mark RUNNING jobs with stale heartbeats as DEAD_LETTERED."""
    stale_threshold = datetime.now(UTC) - timedelta(minutes=2)
    stmt = text("""
        UPDATE core_jobs SET status = :dead_status, error = :error, completed_at = :now
        WHERE status = :running_status
          AND (last_heartbeat IS NULL OR last_heartbeat < :threshold)
          AND (started_at IS NULL OR started_at < :threshold)
    """)
    params = {
        "dead_status": JobStatus.DEAD_LETTERED.value,
        "error": "Stale heartbeat detected: worker failed to update heartbeat within 2 minutes",
        "running_status": JobStatus.RUNNING.value,
        "threshold": stale_threshold,
        "now": datetime.now(UTC),
    }
    if _test_session is not None:
        await _test_session.execute(stmt, params)
        return
    async with get_core_session() as session:
        await session.execute(stmt, params)


async def process_pending_retries() -> None:
    """Reset FAILED jobs whose retry time has passed back to PENDING."""
    now = datetime.now(UTC)
    stmt = text("""
        UPDATE core_jobs SET status = :pending_status
        WHERE status = :failed_status
          AND next_retry_at IS NOT NULL
          AND next_retry_at <= :now
          AND attempt < max_attempts
    """)
    params = {
        "pending_status": JobStatus.PENDING.value,
        "failed_status": JobStatus.FAILED.value,
        "now": now,
    }
    if _test_session is not None:
        await _test_session.execute(stmt, params)
        return
    async with get_core_session() as session:
        await session.execute(stmt, params)


async def dispatch_pending_jobs() -> None:
    """Dispatch jobs stuck in PENDING status to the worker."""
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    stmt = text("""
        SELECT id FROM core_jobs
        WHERE status = :pending_status
          AND created_at < :cutoff
          AND job_type != 'source_sync'
        LIMIT 50
    """)
    params = {"pending_status": JobStatus.PENDING.value, "cutoff": cutoff}

    if _test_session is not None:
        result = await _test_session.execute(stmt, params)
        job_ids = [row[0] for row in result.fetchall()]
    else:
        async with get_core_session() as session:
            result = await session.execute(stmt, params)
            job_ids = [row[0] for row in result.fetchall()]

    if not job_ids:
        return

    worker_url = os.getenv("WORKER_ADMIN_URL", "http://worker:8001")
    dispatched = 0
    async with httpx.AsyncClient() as client:
        for job_id in job_ids:
            try:
                response = await client.post(
                    f"{worker_url}/api/admin/enqueue",
                    json={"job_id": str(job_id)},
                    timeout=10.0,
                )
                if response.status_code < 300:
                    dispatched += 1
                else:
                    logger.warning("Failed to enqueue job %s: %d", job_id, response.status_code)
            except Exception:
                logger.exception("Error enqueuing job %s", job_id)

    if dispatched > 0:
        logger.info("Dispatched %d stuck pending jobs", dispatched)


# ---------------------------------------------------------------------------
# Database backup
# ---------------------------------------------------------------------------


def _parse_db_connection() -> tuple[str, str, str]:
    """Parse host, user, password from DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        msg = "DATABASE_URL not set"
        raise ValueError(msg)
    parsed = urlparse(database_url.replace("+asyncpg", ""))
    return parsed.hostname or "db", parsed.username or "gts", parsed.password or ""


async def _discover_databases(host: str, user: str, password: str) -> list[str]:
    """Discover application databases from PostgreSQL catalog."""
    env = {**os.environ, "PGPASSWORD": password}
    proc = await asyncio.create_subprocess_exec(
        "psql",
        "-h",
        host,
        "-U",
        user,
        "-d",
        "postgres",
        "-t",
        "-A",
        "-c",
        "SELECT datname FROM pg_database WHERE datistemplate = false"
        " AND datname != 'postgres' ORDER BY datname",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        msg = "Database discovery timed out"
        raise RuntimeError(msg)
    if proc.returncode != 0:
        raise RuntimeError(f"Database discovery failed: {stderr.decode().strip()}")
    return [line.strip() for line in stdout.decode().strip().splitlines() if line.strip()]


def _cleanup_old_backups(retention_days: int) -> None:
    """Delete backup files older than retention_days."""
    if not _BACKUPS_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=retention_days)
    for dump_file in _BACKUPS_DIR.glob("*.dump"):
        mtime = datetime.fromtimestamp(dump_file.stat().st_mtime)
        if mtime < cutoff:
            dump_file.unlink()
            logger.info("Deleted old backup: %s", dump_file.name)


async def backup_all_databases() -> None:
    """Discover and back up all application databases."""
    host, user, password = _parse_db_connection()
    databases = await _discover_databases(host, user, password)

    if not databases:
        logger.warning("No databases found to back up")
        return

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    env = {**os.environ, "PGPASSWORD": password}

    for db_name in databases:
        backup_file = _BACKUPS_DIR / f"{db_name}.{timestamp}.dump"
        try:
            with open(backup_file, "wb") as fh:
                proc = await asyncio.create_subprocess_exec(
                    "pg_dump",
                    "-h",
                    host,
                    "-U",
                    user,
                    "-Fc",
                    db_name,
                    stdout=fh,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                try:
                    _, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=300)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    backup_file.unlink(missing_ok=True)
                    logger.error("pg_dump timed out for %s", db_name)
                    continue

            if proc.returncode != 0:
                backup_file.unlink(missing_ok=True)
                logger.error("pg_dump failed for %s: %s", db_name, stderr_data.decode().strip())
                continue

            size = backup_file.stat().st_size
            if size < 100:
                backup_file.unlink(missing_ok=True)
                logger.error("Backup too small for %s — database may be empty", db_name)
                continue

            logger.info("Backed up %s: %s (%.1f MB)", db_name, backup_file.name, size / 1024 / 1024)

        except Exception:
            backup_file.unlink(missing_ok=True)
            logger.exception("Failed to back up %s", db_name)

    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    _cleanup_old_backups(retention_days)
