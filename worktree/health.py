"""Health checking for worktrees."""

from dataclasses import dataclass
from pathlib import Path

from .config import get_main_worktree_path
from .docker import (
    check_backend_health,
    check_nginx_health,
    get_service_status,
)
from .registry import get_worktree_by_path


def _get_expected_services(worktree_path: Path) -> set[str]:
    """Get expected services based on worktree type.

    Main worktree runs jobs profile (redis, worker, scheduler).
    Feature worktrees only run core services (nginx, backend, db).
    """
    # Core services for all worktrees
    expected = {"nginx", "backend", "db"}

    # Main worktree includes jobs profile services
    main_path = get_main_worktree_path()
    if worktree_path.resolve() == main_path.resolve():
        expected.update({"redis", "worker", "scheduler"})

    return expected


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    services: dict[str, str]
    nginx_responding: bool
    backend_responding: bool
    issues: list[str]
    worktree_path: Path | None = None

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
            expected_services = {"nginx", "backend", "db"}
        return all(self.services.get(svc) == "running" for svc in expected_services)


def check_worktree_health(worktree_path: Path) -> HealthCheckResult:
    """Perform comprehensive health check on a worktree.

    Checks:
    1. Docker container status (runtime services must be running)
    2. Nginx HTTP response (user-facing entry point)
    3. Backend HTTP health endpoint (/health)

    Note: Frontend is build-only (--profile build), not part of runtime stack.

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
            backend_responding=False,
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

    # Check backend health endpoint
    backend_responding = check_backend_health(worktree)
    if not backend_responding:
        issues.append(f"Backend not responding at {worktree.backend_url}/health")

    healthy = len(issues) == 0

    return HealthCheckResult(
        healthy=healthy,
        services=services,
        nginx_responding=nginx_responding,
        backend_responding=backend_responding,
        issues=issues,
        worktree_path=worktree_path,
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
