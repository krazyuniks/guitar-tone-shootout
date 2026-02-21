"""Health checking for worktrees."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .backup import get_latest_backups
from .config import get_main_worktree_path
from .docker import (
    check_nginx_health,
    check_webapp_health,
    get_service_status,
)
from .registry import get_worktree_by_path


def _get_expected_services(worktree_path: Path) -> set[str]:
    """Get expected services based on worktree type.

    Main worktree runs jobs profile (redis, worker, t3k-sync, audio-worker, video-worker).
    Feature worktrees only run core services (nginx, webapp, db).
    """
    # Core services for all worktrees
    expected = {"nginx", "webapp", "db", "astro"}

    # Main worktree includes jobs profile services
    main_path = get_main_worktree_path()
    if worktree_path.resolve() == main_path.resolve():
        expected.update({"redis", "worker", "t3k-sync", "audio-worker", "video-worker"})

    return expected


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    services: dict[str, str]
    nginx_responding: bool
    webapp_responding: bool
    issues: list[str]
    worktree_path: Path | None = None
    last_backup: dict[str, datetime | None] = field(default_factory=dict)
    backup_stale: bool = False

    @property
    def status_emoji(self) -> str:
        return "\u25cf" if self.healthy else "\u25cb"  # ● or ○

    @property
    def containers_running(self) -> bool:
        """Check if all runtime containers are running."""
        if self.worktree_path:
            expected_services = _get_expected_services(self.worktree_path)
        else:
            # Fallback for backwards compatibility
            expected_services = {"nginx", "webapp", "db"}
        return all(self.services.get(svc) == "running" for svc in expected_services)


def check_worktree_health(worktree_path: Path) -> HealthCheckResult:
    """Perform comprehensive health check on a worktree.

    Checks:
    1. Docker container status (runtime services must be running)
    2. Nginx HTTP response (user-facing entry point)
    3. Webapp HTTP health endpoint (/health)

    Note: Astro runs as a chokidar watcher (auto-rebuilds on source changes).

    Args:
        worktree_path: Path to the worktree

    Returns:
        HealthCheckResult with status and any issues
    """
    issues = []

    # Get worktree from registry
    try:
        worktree = get_worktree_by_path(worktree_path)
    except Exception as e:
        return HealthCheckResult(
            healthy=False,
            services={},
            nginx_responding=False,
            webapp_responding=False,
            issues=[f"Worktree not registered: {e}"],
        )

    # Check service status
    services = get_service_status(worktree_path)

    # Expected services based on worktree type
    expected_services = _get_expected_services(worktree_path)
    for service in expected_services:
        if service not in services:
            issues.append(f"Service not found: {service}")
        elif services[service] != "running":
            issues.append(f"Service {service} is {services[service]}")

    # Check nginx health (user-facing entry point)
    nginx_responding = check_nginx_health(worktree)
    if not nginx_responding:
        issues.append(f"Nginx not responding at {worktree.nginx_url}")

    # Check webapp health endpoint
    webapp_responding = check_webapp_health(worktree)
    if not webapp_responding:
        issues.append(f"Webapp not responding at {worktree.webapp_url}/health")

    # Check backup status
    backups = get_latest_backups()
    now = datetime.now()
    stale_threshold = now - timedelta(hours=24)
    backup_stale = False

    last_backup: dict[str, datetime | None] = {}
    for db_name, backup_path in backups.items():
        if backup_path:
            mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
            last_backup[db_name] = mtime
            if mtime < stale_threshold:
                backup_stale = True
        else:
            last_backup[db_name] = None
            backup_stale = True

    healthy = len(issues) == 0

    return HealthCheckResult(
        healthy=healthy,
        services=services,
        nginx_responding=nginx_responding,
        webapp_responding=webapp_responding,
        issues=issues,
        worktree_path=worktree_path,
        last_backup=last_backup,
        backup_stale=backup_stale,
    )


def quick_health_check(worktree_path: Path) -> bool:
    """Quick health check - just checks if services are running.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if all expected runtime services are running
    """
    services = get_service_status(worktree_path)
    expected = _get_expected_services(worktree_path)

    return all(services.get(service) == "running" for service in expected)
