"""Health checking for worktrees."""

from dataclasses import dataclass
from pathlib import Path

from .docker import (
    check_backend_health,
    get_container_logs,
    get_service_status,
)
from .registry import get_worktree_by_path


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    services: dict[str, str]
    backend_responding: bool
    issues: list[str]

    @property
    def status_emoji(self) -> str:
        return "\u25cf" if self.healthy else "\u25cb"  # ● or ○


def check_worktree_health(worktree_path: Path) -> HealthCheckResult:
    """Perform comprehensive health check on a worktree.

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
            backend_responding=False,
            issues=[f"Worktree not registered: {e}"],
        )

    # Check service status
    services = get_service_status(worktree_path)

    expected_services = {"backend", "frontend", "db", "redis"}
    for service in expected_services:
        if service not in services:
            issues.append(f"Service not found: {service}")
        elif services[service] != "running":
            issues.append(f"Service {service} is {services[service]}")

    # Check backend health endpoint
    backend_responding = check_backend_health(worktree)
    if not backend_responding:
        issues.append(f"Backend not responding at {worktree.backend_url}/health")

    healthy = len(issues) == 0

    return HealthCheckResult(
        healthy=healthy,
        services=services,
        backend_responding=backend_responding,
        issues=issues,
    )


def get_detailed_health(worktree_path: Path) -> dict:
    """Get detailed health information including logs.

    Args:
        worktree_path: Path to the worktree

    Returns:
        Dict with health status and recent logs from unhealthy services
    """
    result = check_worktree_health(worktree_path)

    details = {
        "healthy": result.healthy,
        "services": result.services,
        "backend_responding": result.backend_responding,
        "issues": result.issues,
        "logs": {},
    }

    # Get logs for unhealthy services
    for service, status in result.services.items():
        if status != "running":
            details["logs"][service] = get_container_logs(
                worktree_path, service, lines=20
            )

    return details


def quick_health_check(worktree_path: Path) -> bool:
    """Quick health check - just checks if services are running.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if all expected services are running
    """
    services = get_service_status(worktree_path)
    expected = {"backend", "frontend", "db", "redis"}

    for service in expected:
        if services.get(service) != "running":
            return False

    return True
