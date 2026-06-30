"""Scheduled background tasks for the t3k-sync container."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from sqlalchemy import column, delete, table, text

from gts.domain.auth_gate import check_auth_status
from gts.domain.value_objects.job_status import JobStatus
from gts.domain.value_objects.source_auth_status import SourceAuthStatus
from messaging.db import get_core_session
from t3k_sync.source_sync import _PG_ADVISORY_LOCK_KEY

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from source_t3k.adapters.inbound.token_manager import T3KTokenManager

logger = logging.getLogger(__name__)

_REFRESH_WINDOW_SECONDS = 600
_FALLBACK_REFRESH_SECONDS = 1800
_BACKUPS_DIR = Path("/app/backups")
_DISPATCH_MAX_FAILURES = 3
_DISPATCH_COOLDOWN = timedelta(minutes=30)
# pgmq archive table names are a_ + alphanumeric/underscore (from system catalog, not user input).
_PGMQ_ARCHIVE_TABLE_RE = re.compile(r"^a_[a-z][a-z0-9_]*$")

# Test hook: set by tests to inject the test session into DB tasks.
# Allows task functions to share the test's SAVEPOINT-isolated session.
_test_session: AsyncSession | None = None

# In-memory cooldown tracker for dispatch_pending_jobs.
# Maps job_id -> (failure_count, last_failure_time).
_dispatch_failures: dict[UUID, tuple[int, datetime]] = {}


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
    *,
    token_manager: T3KTokenManager | None = None,
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
        logger.debug("Auth login_required — skipping refresh (run `just t3k-auth`)")
        return
    if status == SourceAuthStatus.UNKNOWN and not Path(auth_file_path).exists():
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

    if token_manager is None and not encryption_key:
        logger.error("OAUTH_ENCRYPTION_KEY not set — cannot refresh")
        return

    _update_auth_status(auth_file_path, SourceAuthStatus.EXPIRING_SOON)

    from source_t3k.adapters.inbound.exceptions import T3KAPIError
    from source_t3k.adapters.inbound.token_manager import T3KTokenManager

    _owns_tm = token_manager is None
    effective_tm: T3KTokenManager = token_manager or T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    new_status = SourceAuthStatus.REFRESH_FAILED
    try:
        await effective_tm.get_access_token()
        new_status = SourceAuthStatus.VALID
        logger.info("T3K token refreshed successfully")
    except T3KAPIError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "re-authenticate" in error_msg.lower():
            new_status = SourceAuthStatus.LOGIN_REQUIRED
            logger.error("T3K refresh token expired — run `just t3k-auth`")
        else:
            new_status = SourceAuthStatus.REFRESH_FAILED
            logger.warning("T3K token refresh failed: %s", error_msg)
    except Exception:
        new_status = SourceAuthStatus.REFRESH_FAILED
        logger.exception("Unexpected error during T3K token refresh")
    finally:
        if _owns_tm:
            await effective_tm.close()

    _update_auth_status(auth_file_path, new_status)


# ---------------------------------------------------------------------------
# Job monitoring
# ---------------------------------------------------------------------------


async def monitor_stale_jobs() -> None:
    """Mark RUNNING jobs with stale heartbeats as DEAD_LETTERED.

    For SOURCE_SYNC jobs, checks the advisory lock before marking dead.
    If the lock is held, the sync is still alive regardless of heartbeat.
    """
    stale_threshold = datetime.now(UTC) - timedelta(minutes=2)
    now = datetime.now(UTC)

    # Non-SOURCE_SYNC jobs: heartbeat-only check (unchanged behaviour)
    non_sync_stmt = text("""
        UPDATE core_jobs SET status = :dead_status, error = :error, completed_at = :now
        WHERE status = :running_status
          AND job_type != 'source_sync'
          AND (last_heartbeat IS NULL OR last_heartbeat < :threshold)
          AND (started_at IS NULL OR started_at < :threshold)
    """)
    non_sync_params = {
        "dead_status": JobStatus.DEAD_LETTERED.value,
        "error": "Stale heartbeat detected: worker failed to update heartbeat within 2 minutes",
        "running_status": JobStatus.RUNNING.value,
        "threshold": stale_threshold,
        "now": now,
    }

    # SOURCE_SYNC jobs: check advisory lock before killing
    sync_check_stmt = text("""
        SELECT id FROM core_jobs
        WHERE status = :running_status
          AND job_type = 'source_sync'
          AND (last_heartbeat IS NULL OR last_heartbeat < :threshold)
          AND (started_at IS NULL OR started_at < :threshold)
    """)
    sync_check_params = {
        "running_status": JobStatus.RUNNING.value,
        "threshold": stale_threshold,
    }

    if _test_session is not None:
        await _test_session.execute(non_sync_stmt, non_sync_params)
        # In tests we can't probe advisory locks across sessions,
        # so skip SOURCE_SYNC lock check — tests use non-sync job types.
        return

    async with get_core_session() as session:
        await session.execute(non_sync_stmt, non_sync_params)

        # Check if any SOURCE_SYNC jobs look stale
        result = await session.execute(sync_check_stmt, sync_check_params)
        stale_sync_ids = [row[0] for row in result.fetchall()]
        if not stale_sync_ids:
            return

    # Probe the advisory lock in a separate session (non-transactional).
    # pg_try_advisory_lock acquires if free — we must release immediately.
    from messaging.db import get_core_session_no_tx

    async with get_core_session_no_tx() as lock_session:
        lock_result = await lock_session.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
        )
        lock_free = lock_result.scalar()
        if lock_free:
            # Lock was free — sync truly died. Release our test lock.
            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _PG_ADVISORY_LOCK_KEY}
            )
            # Mark the stale SOURCE_SYNC jobs as dead
            async with get_core_session() as session:
                kill_stmt = text("""
                    UPDATE core_jobs SET status = :dead_status, error = :error, completed_at = :now
                    WHERE id = ANY(:ids) AND status = :running_status
                """)
                await session.execute(
                    kill_stmt,
                    {
                        "dead_status": JobStatus.DEAD_LETTERED.value,
                        "error": "Stale heartbeat detected: sync lock free, worker died",
                        "running_status": JobStatus.RUNNING.value,
                        "now": now,
                        "ids": stale_sync_ids,
                    },
                )
        else:
            # Lock held — sync is alive, just slow. Update heartbeat to prevent
            # re-checking every cycle.
            async with get_core_session() as session:
                touch_stmt = text("""
                    UPDATE core_jobs SET last_heartbeat = :now
                    WHERE id = ANY(:ids) AND status = :running_status
                """)
                await session.execute(
                    touch_stmt,
                    {
                        "now": now,
                        "running_status": JobStatus.RUNNING.value,
                        "ids": stale_sync_ids,
                    },
                )


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
    """Dispatch jobs stuck in PENDING status to the worker.

    Tracks consecutive failures per job ID. After 3 consecutive 400s,
    the job is skipped for 30 minutes to avoid log spam.
    """
    # Expire old cooldowns
    now = datetime.now(UTC)
    expired = [
        jid for jid, (count, ts) in _dispatch_failures.items() if now - ts > _DISPATCH_COOLDOWN
    ]
    for jid in expired:
        del _dispatch_failures[jid]

    cutoff = now - timedelta(minutes=5)
    # Only dispatch job types that the enqueue endpoint can handle.
    # source_sync is self-managed; notification has no handler.
    dispatchable = ("shootout", "shootout_audio", "shootout_master", "audio_processing")
    placeholders = ", ".join(f":jt{i}" for i in range(len(dispatchable)))
    stmt = text(f"""
        SELECT id FROM core_jobs
        WHERE status = :pending_status
          AND created_at < :cutoff
          AND job_type IN ({placeholders})
        LIMIT 50
    """)
    params = {
        "pending_status": JobStatus.PENDING.value,
        "cutoff": cutoff,
        **{f"jt{i}": jt for i, jt in enumerate(dispatchable)},
    }

    if _test_session is not None:
        result = await _test_session.execute(stmt, params)
        job_ids = [row[0] for row in result.fetchall()]
    else:
        async with get_core_session() as session:
            result = await session.execute(stmt, params)
            job_ids = [row[0] for row in result.fetchall()]

    if not job_ids:
        return

    # Filter out jobs in cooldown
    eligible = [
        jid
        for jid in job_ids
        if jid not in _dispatch_failures or _dispatch_failures[jid][0] < _DISPATCH_MAX_FAILURES
    ]
    if not eligible:
        return

    worker_url = os.getenv("WORKER_ADMIN_URL", "http://webapp:8000")
    dispatched = 0
    async with httpx.AsyncClient() as client:
        for job_id in eligible:
            try:
                response = await client.post(
                    f"{worker_url}/api/admin/enqueue",
                    json={"job_id": str(job_id)},
                    timeout=10.0,
                )
                if response.status_code < 300:
                    dispatched += 1
                    _dispatch_failures.pop(job_id, None)
                else:
                    prev_count, _ = _dispatch_failures.get(job_id, (0, now))
                    _dispatch_failures[job_id] = (prev_count + 1, now)
                    if prev_count + 1 >= _DISPATCH_MAX_FAILURES:
                        logger.warning(
                            "Job %s failed dispatch %d times, cooling down for %d min",
                            job_id,
                            prev_count + 1,
                            int(_DISPATCH_COOLDOWN.total_seconds() / 60),
                        )
                    else:
                        logger.warning("Failed to enqueue job %s: %d", job_id, response.status_code)
            except Exception:
                logger.exception("Error enqueuing job %s", job_id)

    if dispatched > 0:
        logger.info("Dispatched %d stuck pending jobs", dispatched)


# ---------------------------------------------------------------------------
# Retention / purge
# ---------------------------------------------------------------------------


async def purge_pgmq_archives() -> None:
    """Delete pgmq archive rows older than PGMQ_ARCHIVE_RETENTION_DAYS (default: 30)."""
    retention_days = int(os.getenv("PGMQ_ARCHIVE_RETENTION_DAYS", "30"))
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    discover_stmt = text(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'pgmq' AND table_name LIKE 'a_%' AND table_type = 'BASE TABLE'"
    )

    async def _purge(session: AsyncSession) -> int:
        result = await session.execute(discover_stmt)
        table_names = [row[0] for row in result.fetchall()]
        total = 0
        for table_name in table_names:
            if not _PGMQ_ARCHIVE_TABLE_RE.match(table_name):
                logger.warning("Skipping unexpected pgmq archive table: %r", table_name)
                continue
            # Use SQLAlchemy's structured expression API so the table identifier
            # is quoted by the dialect rather than interpolated into a raw SQL string.
            archive_tbl = table(table_name, column("archived_at"), schema="pgmq")
            del_result = await session.execute(
                delete(archive_tbl).where(archive_tbl.c.archived_at < cutoff)
            )
            total += del_result.rowcount
        return total

    if _test_session is not None:
        deleted = await _purge(_test_session)
    else:
        async with get_core_session() as session:
            deleted = await _purge(session)
            await session.commit()

    if deleted:
        logger.info("Purged %d rows from pgmq archives (cutoff: %s)", deleted, cutoff.date())


async def purge_old_jobs() -> None:
    """Delete terminal core_jobs older than JOB_RETENTION_DAYS (default: 90)."""
    retention_days = int(os.getenv("JOB_RETENTION_DAYS", "90"))
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    terminal = [
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.DEAD_LETTERED.value,
    ]
    stmt = text(
        "DELETE FROM core_jobs"
        " WHERE status = ANY(:statuses)"
        " AND completed_at IS NOT NULL"
        " AND completed_at < :cutoff"
    )
    params: dict[str, object] = {"statuses": terminal, "cutoff": cutoff}

    if _test_session is not None:
        result = await _test_session.execute(stmt, params)
        deleted = result.rowcount
    else:
        async with get_core_session() as session:
            result = await session.execute(stmt, params)
            await session.commit()
            deleted = result.rowcount

    if deleted:
        logger.info("Purged %d terminal jobs (cutoff: %s)", deleted, cutoff.date())


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
    """Discover and back up all application databases.

    On full success, runs retention purges (pgmq archives and terminal jobs)
    so they are always sequenced after a confirmed backup, never before or
    concurrently with it.
    """
    host, user, password = _parse_db_connection()
    databases = await _discover_databases(host, user, password)

    if not databases:
        logger.warning("No databases found to back up")
        return

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    env = {**os.environ, "PGPASSWORD": password}

    failed: list[str] = []
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
                    failed.append(db_name)
                    continue

            if proc.returncode != 0:
                backup_file.unlink(missing_ok=True)
                logger.error("pg_dump failed for %s: %s", db_name, stderr_data.decode().strip())
                failed.append(db_name)
                continue

            size = backup_file.stat().st_size
            if size < 100:
                backup_file.unlink(missing_ok=True)
                logger.error("Backup too small for %s — database may be empty", db_name)
                failed.append(db_name)
                continue

            logger.info("Backed up %s: %s (%.1f MB)", db_name, backup_file.name, size / 1024 / 1024)

        except Exception:
            backup_file.unlink(missing_ok=True)
            logger.exception("Failed to back up %s", db_name)
            failed.append(db_name)

    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    _cleanup_old_backups(retention_days)

    if failed:
        logger.warning(
            "Skipping retention purge — %d database backup(s) failed: %s",
            len(failed),
            ", ".join(failed),
        )
        return

    await purge_pgmq_archives()
    await purge_old_jobs()
