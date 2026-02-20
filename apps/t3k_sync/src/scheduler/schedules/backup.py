"""Scheduled database backups."""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BACKUPS_DIR = Path("/app/backups")


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
            with open(backup_file, "wb") as file_handle:
                proc = await asyncio.create_subprocess_exec(
                    "pg_dump",
                    "-h",
                    host,
                    "-U",
                    user,
                    "-Fc",
                    db_name,
                    stdout=file_handle,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                try:
                    _, stderr_data = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=300,
                    )
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    backup_file.unlink(missing_ok=True)
                    logger.error("pg_dump timed out for %s", db_name)
                    continue

            if proc.returncode != 0:
                backup_file.unlink(missing_ok=True)
                logger.error(
                    "pg_dump failed for %s: %s",
                    db_name,
                    stderr_data.decode().strip(),
                )
                continue

            size = backup_file.stat().st_size
            if size < 100:
                backup_file.unlink(missing_ok=True)
                logger.error("Backup too small for %s — database may be empty", db_name)
                continue

            size_mb = size / (1024 * 1024)
            logger.info("Backed up %s: %s (%.1f MB)", db_name, backup_file.name, size_mb)

        except Exception:
            backup_file.unlink(missing_ok=True)
            logger.exception("Failed to back up %s", db_name)

    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    _cleanup_old_backups(retention_days)


backup_all_databases.labels = {"schedule": [{"interval": 43200}]}  # type: ignore[attr-defined]
