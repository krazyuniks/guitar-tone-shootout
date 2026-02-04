"""Health checking for worktrees."""

from dataclasses import dataclass
from pathlib import Path

from .docker import (
    check_backend_health,
    check_nginx_health,
    get_service_status,
)
from .registry import get_worktree_by_path


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    services: dict[str, str]
    nginx_responding: bool
    backend_responding: bool
    issues: list[str]

    @property
    def status_emoji(self) -> str:
        return "\u25cf" if self.healthy else "\u25cb"  # ● or ○

    @property
    def containers_running(self) -> bool:
        """Check if all runtime containers are running."""
        expected_services = {"nginx", "backend", "db", "redis", "worker", "scheduler"}
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

    # Runtime services (frontend is build-only with --profile build)
    expected_services = {"nginx", "backend", "db", "redis", "worker", "scheduler"}
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
    )


def quick_health_check(worktree_path: Path) -> bool:
    """Quick health check - just checks if services are running.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if all expected runtime services are running
    """
    services = get_service_status(worktree_path)
    # Runtime services (frontend is build-only with --profile build)
    expected = {"nginx", "backend", "db", "redis", "worker", "scheduler"}

    return all(services.get(service) == "running" for service in expected)
