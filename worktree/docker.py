"""Docker Compose operations for worktree management."""

import contextlib
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import get_main_worktree_path, settings
from .registry import Worktree


class DockerError(Exception):
    """Docker operation failed."""


def is_traefik_running() -> bool:
    """Check if Traefik reverse proxy is running.

    Returns:
        True if traefik container is running
    """
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", "name=traefik"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def run_compose(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command.

    Compose files are configured via COMPOSE_FILE in .env (set by worktree.py setup).
    Docker Compose auto-loads .env when present.

    Args:
        args: docker compose arguments (without 'docker compose' prefix)
        cwd: Working directory (worktree path)
        env: Additional environment variables
        check: Raise exception on non-zero exit
        capture_output: Capture stdout/stderr
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess result

    Raises:
        DockerError: If check=True and command fails
    """
    import os

    cmd = ["docker", "compose", *args]

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=full_env,
            capture_output=capture_output,
            text=True,
            check=check,
            timeout=timeout or settings.docker_timeout,
        )
        return result
    except subprocess.CalledProcessError as e:
        raise DockerError(f"Docker compose failed: {' '.join(cmd)}\n{e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise DockerError(f"Docker compose timed out: {' '.join(cmd)}") from e


def cleanup_containers(worktree_path: Path) -> None:
    """Clean up orphaned containers before starting services.

    This ensures idempotent setup by removing any leftover containers
    from previous failed attempts.

    Args:
        worktree_path: Path to the worktree
    """
    run_compose(
        ["down", "--remove-orphans"],
        cwd=worktree_path,
        check=False,  # Don't fail if nothing to clean
    )


def start_services(worktree_path: Path, detach: bool = True, cleanup: bool = True) -> None:
    """Start all Docker services for a worktree.

    Args:
        worktree_path: Path to the worktree
        detach: Run in background
        cleanup: Run cleanup before starting (default True for idempotency)

    Note:
        Main worktree includes background job services (worker, t3k-sync,
        audio-worker, video-worker) via --profile jobs. Feature branches
        don't need them.
    """
    if cleanup:
        cleanup_containers(worktree_path)

    args = []

    # Main worktree runs background jobs (worker, t3k-sync, audio-worker, video-worker)
    # Feature branches don't need them - they use data synced from main
    main_path = get_main_worktree_path()
    if worktree_path.resolve() == main_path.resolve():
        args.extend(["--profile", "jobs"])

    args.append("up")
    if detach:
        args.append("-d")

    run_compose(args, cwd=worktree_path, timeout=120)


def stop_services(worktree_path: Path, timeout: int = 30) -> None:
    """Stop all Docker services for a worktree.

    Args:
        worktree_path: Path to the worktree
        timeout: Shutdown timeout in seconds
    """
    run_compose(
        ["down", "--timeout", str(timeout)],
        cwd=worktree_path,
        timeout=timeout + 30,  # Allow extra time
    )


def stop_services_graceful(
    worktree_path: Path,
    timeout: int = 30,
    force_timeout: int = 10,
) -> bool:
    """Gracefully stop all Docker services with SIGTERM, then SIGKILL if needed.

    This function handles services with stop_grace_period properly:
    1. First sends SIGTERM via `docker compose stop` to allow graceful shutdown
    2. Waits for the timeout period
    3. If services don't stop, forces removal with shorter timeout

    This prevents the timeout issues that occur when calling `docker compose down -v`
    directly on services that have long stop_grace_period values.

    Args:
        worktree_path: Path to the worktree
        timeout: Graceful shutdown timeout in seconds (default: 30)
        force_timeout: Force shutdown timeout in seconds (default: 10)

    Returns:
        True if all services stopped successfully
    """
    # Step 1: Send SIGTERM via docker compose stop
    with contextlib.suppress(DockerError):
        run_compose(
            ["stop", "--timeout", str(timeout)],
            cwd=worktree_path,
            timeout=timeout + 30,  # Allow extra time beyond the stop timeout
            check=False,  # Don't fail if some services don't stop
        )

    # Step 2: Check if any containers are still running
    status = get_service_status(worktree_path)
    still_running = [service for service, state in status.items() if state == "running"]

    if still_running:
        # Step 3: Force stop any remaining containers
        with contextlib.suppress(DockerError):
            run_compose(
                ["stop", "--timeout", str(force_timeout)],
                cwd=worktree_path,
                timeout=force_timeout + 10,
                check=False,
            )

    return True


def remove_volumes(worktree: Worktree, worktree_path: Path) -> None:
    """Remove Docker volumes and networks for a worktree.

    This function properly handles teardown by:
    1. First gracefully stopping services (handles stop_grace_period)
    2. Then calling `docker compose down -v --remove-orphans` to clean up

    Args:
        worktree: Worktree configuration (unused, kept for API compatibility)
        worktree_path: Path to the worktree
    """
    from worktree.config import settings

    # Step 1: Gracefully stop services first
    # This prevents timeout issues with services that have long stop_grace_period
    stop_services_graceful(worktree_path, timeout=30, force_timeout=10)

    # Step 2: Use docker compose down -v to remove containers, networks, AND volumes
    # The --remove-orphans flag handles containers from previous failed teardowns
    # Use configured timeout for cleanup operations
    docker_timeout = settings.docker_timeout
    run_compose(
        ["down", "-v", "--remove-orphans", "--timeout", str(docker_timeout)],
        cwd=worktree_path,
        timeout=docker_timeout + 30,  # Allow extra time for cleanup after shutdown
    )


def get_service_status(worktree_path: Path) -> dict[str, str]:
    """Get status of all services.

    Args:
        worktree_path: Path to the worktree

    Returns:
        Dict mapping service names to status (running, exited, etc.)
    """
    try:
        result = run_compose(
            ["ps", "--format", "{{.Service}}:{{.State}}"],
            cwd=worktree_path,
            check=False,
        )

        status = {}
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                service, state = line.split(":", 1)
                status[service] = state

        return status
    except DockerError:
        return {}


def is_healthy(worktree_path: Path) -> bool:
    """Check if all services are running and healthy.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if all expected services are running
    """
    status = get_service_status(worktree_path)

    # Core runtime services for feature worktrees (no Redis - it's in jobs profile)
    # Astro runs as a chokidar file watcher (auto-rebuilds on source changes)
    expected_services = {"nginx", "webapp", "db", "astro"}

    # Worker, t3k-sync, audio-worker, video-worker, and Redis only run on main worktree (via --profile jobs)
    main_path = get_main_worktree_path()
    if worktree_path.resolve() == main_path.resolve():
        expected_services.update({"worker", "t3k-sync", "audio-worker", "video-worker", "redis"})

    for service in expected_services:
        if service not in status:
            return False
        if status[service] != "running":
            return False

    return True


def wait_for_healthy(
    worktree_path: Path,
    timeout: int | None = None,
    poll_interval: float = 0.5,
) -> bool:
    """Wait for services to become healthy.

    Args:
        worktree_path: Path to the worktree
        timeout: Maximum wait time in seconds
        poll_interval: Seconds between checks

    Returns:
        True if healthy within timeout, False otherwise
    """
    timeout = timeout or settings.health_timeout
    start = time.time()

    while time.time() - start < timeout:
        if is_healthy(worktree_path):
            return True
        time.sleep(poll_interval)

    return False


def check_nginx_health(worktree: Worktree) -> bool:
    """Check if nginx responds to HTTP requests.

    Args:
        worktree: Worktree configuration

    Returns:
        True if nginx is responding
    """
    import urllib.error
    import urllib.request
    from http.client import RemoteDisconnected

    # Check nginx by requesting /health (which it proxies to webapp)
    url = f"{worktree.nginx_url}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return bool(response.status == 200)
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        RemoteDisconnected,
        OSError,
    ):
        return False


def check_webapp_health(worktree: Worktree) -> bool:
    """Check if webapp health endpoint responds.

    Args:
        worktree: Worktree configuration

    Returns:
        True if webapp is healthy
    """
    import urllib.error
    import urllib.request
    from http.client import RemoteDisconnected

    url = f"{worktree.webapp_url}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return bool(response.status == 200)
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        RemoteDisconnected,
        OSError,
    ):
        return False


def check_video_health(worktree: Worktree) -> bool:
    """Check if video service health endpoint responds.

    Args:
        worktree: Worktree configuration

    Returns:
        True if video service is healthy
    """
    try:
        import httpx

        url = f"http://localhost:{worktree.ports.video}/health"
        response = httpx.get(url, timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_frontend_health(worktree: Worktree) -> bool:
    """Check if frontend responds to HTTP requests.

    Args:
        worktree: Worktree configuration

    Returns:
        True if frontend is responding
    """
    import urllib.error
    import urllib.request
    from http.client import RemoteDisconnected

    url = worktree.frontend_url
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            # Any 2xx or 3xx response is good - frontend is serving
            return bool(200 <= response.status < 400)
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        RemoteDisconnected,
        OSError,
    ):
        return False


def wait_for_frontend(
    worktree: Worktree,
    timeout: int = 60,
    initial_delay: float = 1.0,
    max_delay: float = 3.0,
    backoff_factor: float = 1.5,
) -> bool:
    """Wait for frontend to respond to HTTP requests with exponential backoff.

    Args:
        worktree: Worktree configuration
        timeout: Maximum wait time in seconds (default 60)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry

    Returns:
        True if frontend became responsive within timeout, False otherwise
    """
    start = time.time()
    delay = initial_delay

    while time.time() - start < timeout:
        if check_frontend_health(worktree):
            return True
        time.sleep(delay)
        delay = min(delay * backoff_factor, max_delay)

    return False


def wait_for_services_ready(
    worktree: Worktree,
    worktree_path: Path,
    timeout: int = 60,
) -> tuple[bool, list[str]]:
    """Wait for all runtime services (Docker + HTTP endpoints) to be ready.

    This is a comprehensive health check that:
    1. Waits for Docker containers to be running
    2. Waits for webapp HTTP endpoint to respond

    Args:
        worktree: Worktree configuration
        worktree_path: Path to the worktree
        timeout: Maximum wait time in seconds

    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    start = time.time()
    remaining: float = timeout

    # Phase 1: Wait for Docker containers (should be fast — they just started)
    if not wait_for_healthy(worktree_path, timeout=int(min(remaining, 30))):
        issues.append("Docker containers not healthy")
        return False, issues

    remaining = timeout - (time.time() - start)
    if remaining <= 0:
        issues.append("Timeout waiting for Docker")
        return False, issues

    # Phase 2: Wait for webapp HTTP
    if not wait_for_webapp(worktree, timeout=min(int(remaining), 20)):
        issues.append(f"Backend not responding at {worktree.webapp_url}/health")
        return False, issues

    return True, []


def wait_for_webapp(
    worktree: Worktree,
    timeout: int = 60,
    initial_delay: float = 1.0,
    max_delay: float = 5.0,
    backoff_factor: float = 1.5,
) -> bool:
    """Wait for webapp to become healthy with exponential backoff.

    Args:
        worktree: Worktree configuration
        timeout: Maximum wait time in seconds (default 60)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry

    Returns:
        True if webapp became healthy within timeout, False otherwise
    """
    start = time.time()
    delay = initial_delay

    while time.time() - start < timeout:
        if check_webapp_health(worktree):
            return True
        time.sleep(delay)
        delay = min(delay * backoff_factor, max_delay)

    return False


def run_migrations(worktree_path: Path) -> bool:
    """Run database migrations.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if migrations succeeded
    """
    try:
        run_compose(
            ["exec", "-T", "webapp", "alembic", "upgrade", "head"],
            cwd=worktree_path,
        )
        return True
    except DockerError:
        return False


def get_container_logs(
    worktree_path: Path,
    service: str,
    lines: int = 50,
) -> str:
    """Get recent logs from a service.

    Args:
        worktree_path: Path to the worktree
        service: Service name
        lines: Number of lines to retrieve

    Returns:
        Log output
    """
    try:
        result = run_compose(
            ["logs", "--tail", str(lines), service],
            cwd=worktree_path,
        )
        return result.stdout
    except DockerError:
        return ""


def build_images(worktree_path: Path, no_cache: bool = False) -> None:
    """Build Docker images for a worktree.

    Args:
        worktree_path: Path to the worktree
        no_cache: Build without cache
    """
    args = ["build"]
    if no_cache:
        args.append("--no-cache")

    run_compose(args, cwd=worktree_path, timeout=600)  # 10 min timeout for builds


def collect_container_logs(
    worktree_path: Path,
    services: list[str] | None = None,
    lines: int = 100,
) -> dict[str, str]:
    """Collect logs from multiple containers.

    Args:
        worktree_path: Path to the worktree
        services: List of service names (default: based on worktree type)
        lines: Number of lines to retrieve per service

    Returns:
        Dict mapping service name to log content
    """
    if services is None:
        # Core services for feature worktrees (astro is the chokidar file watcher)
        services = ["nginx", "webapp", "db", "astro"]

        # Main worktree includes jobs profile services (redis, worker, t3k-sync, audio-worker, video-worker)
        main_path = get_main_worktree_path()
        if worktree_path.resolve() == main_path.resolve():
            services.extend(["redis", "worker", "t3k-sync", "audio-worker", "video-worker"])

    logs = {}
    for service in services:
        logs[service] = get_container_logs(worktree_path, service, lines)

    return logs


def format_failure_report(
    issues: list[str],
    logs: dict[str, str],
    services: dict[str, str] | None = None,
) -> str:
    """Format a human-readable failure report.

    Args:
        issues: List of issue descriptions
        logs: Dict mapping service name to log content
        services: Dict mapping service name to status (optional)

    Returns:
        Formatted report string
    """

    lines = []
    lines.append("=" * 60)
    lines.append("INFRASTRUCTURE FAILURE REPORT")
    lines.append(f"Time: {datetime.now().isoformat()}")
    lines.append("=" * 60)

    # Issues section
    lines.append("\n[ISSUES]")
    for issue in issues:
        lines.append(f"  • {issue}")

    # Service status section
    if services:
        lines.append("\n[SERVICE STATUS]")
        for service, status in services.items():
            icon = "✓" if status == "running" else "✗"
            lines.append(f"  {icon} {service}: {status}")

    # Logs section
    lines.append("\n[CONTAINER LOGS]")
    for service, log_content in logs.items():
        if log_content.strip():
            lines.append(f"\n--- {service} (last lines) ---")
            # Indent log content
            for log_line in log_content.strip().split("\n")[-50:]:  # Last 50 lines
                lines.append(f"  {log_line}")
        else:
            lines.append(f"\n--- {service} ---")
            lines.append("  (no logs available)")

    lines.append("\n" + "=" * 60)
    lines.append("END OF REPORT")
    lines.append("=" * 60)

    return "\n".join(lines)


def stop_single_service(worktree_path: Path, service: str, timeout: int = 30) -> bool:
    """Stop a single Docker service.

    Args:
        worktree_path: Path to the worktree
        service: Service name to stop
        timeout: Shutdown timeout in seconds

    Returns:
        True if service was stopped successfully
    """
    try:
        run_compose(
            ["stop", "--timeout", str(timeout), service],
            cwd=worktree_path,
            timeout=timeout + 30,
        )
        return True
    except DockerError:
        return False


def start_single_service(worktree_path: Path, service: str) -> bool:
    """Start a single Docker service.

    Args:
        worktree_path: Path to the worktree
        service: Service name to start

    Returns:
        True if service was started successfully
    """
    try:
        run_compose(["start", service], cwd=worktree_path)
        return True
    except DockerError:
        return False


# =============================================================================
# Orphan Container Detection and Cleanup
# =============================================================================


@dataclass
class OrphanedContainer:
    """A Docker container from a worktree that no longer exists in the registry."""

    container_id: str
    container_name: str
    compose_project: str
    service: str
    ports: list[str]  # List of port mappings like "127.0.0.1:6381->6379/tcp"
    status: str


@dataclass
class OrphanedNetwork:
    """A Docker network from a worktree that no longer exists in the registry."""

    network_id: str
    network_name: str
    compose_project: str
    subnet: str | None


def find_orphaned_networks() -> list[OrphanedNetwork]:
    """Find GTS Docker networks that don't belong to registered worktrees.

    These are networks from worktrees that were deleted without proper teardown.
    Networks matching the pattern *_default with GTS subnets (10.10.x.0/24) are checked.

    Returns:
        List of OrphanedNetwork objects for untracked networks.
    """
    import json

    from .registry import list_worktrees

    # Get all registered worktree names (directory names used by docker compose)
    # Docker Compose uses directory name as project name by default, which becomes
    # the network name prefix (e.g., "main" directory -> "main_default" network)
    registered = list_worktrees(include_removed=False)
    registered_names = {wt.worktree_name for wt in registered}

    # Also include well-known project names that should not be cleaned
    registered_names.add("main")
    registered_names.add("bridge")  # Docker's default bridge network

    orphans = []

    try:
        # Get all networks
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.ID}}\t{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []

        for line in result.stdout.strip().splitlines():
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            network_id, network_name = parts

            # Only check networks ending with _default (compose default networks)
            if not network_name.endswith("_default"):
                continue

            # Extract project name from network name (directory name)
            compose_project = network_name.rsplit("_default", 1)[0]

            # Skip if this is a registered worktree's network
            if compose_project in registered_names:
                continue

            # Check if this is a GTS network by inspecting subnet
            try:
                inspect_result = subprocess.run(
                    ["docker", "network", "inspect", network_id],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if inspect_result.returncode == 0:
                    network_info = json.loads(inspect_result.stdout)
                    if network_info:
                        ipam_config = network_info[0].get("IPAM", {}).get("Config", [])
                        subnet = ipam_config[0].get("Subnet") if ipam_config else None

                        # Only consider networks with GTS subnets (10.10.x.0/24)
                        # or issue-number prefixed names
                        is_gts_subnet = subnet and subnet.startswith("10.10.")
                        is_issue_prefixed = compose_project.split("-")[0].isdigit()

                        if is_gts_subnet or is_issue_prefixed:
                            orphans.append(
                                OrphanedNetwork(
                                    network_id=network_id,
                                    network_name=network_name,
                                    compose_project=compose_project,
                                    subnet=subnet,
                                )
                            )
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                pass

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return []

    return orphans


def find_orphaned_containers() -> list[OrphanedContainer]:
    """Find GTS Docker containers that don't belong to registered worktrees.

    These are containers from worktrees that were deleted without proper teardown,
    or whose registry entries were lost.

    Returns:
        List of OrphanedContainer objects for untracked containers.
    """
    from .registry import list_worktrees

    # Get all registered compose projects
    registered = list_worktrees(include_removed=False)
    registered_projects = {wt.compose_project for wt in registered}

    # Get all running GTS containers
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=gts-",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Ports}}\t{{.State}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return []

    orphans = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        container_id, container_name, ports, status = parts

        # Extract compose project from container name
        # Format: gts-<service>-<worktree> (e.g., gts-db-main, gts-webapp-612-epic-di)
        # We need to extract compose_project as gts-<worktree>
        name_parts = container_name.split("-")
        if len(name_parts) < 3:
            continue

        # Known services
        known_services = {
            "db",
            "redis",
            "webapp",
            "nginx",
            "worker",
            "t3k-sync",
            "audio-worker",
            "video-worker",  # Runtime services
            "astro",
            "cloudbeaver",  # Build-only and tool services
        }

        # Find service name (should be at index 1 after "gts")
        service = None
        service_idx = None
        for i, part in enumerate(name_parts):
            if part in known_services:
                service = part
                service_idx = i
                break

        if not service or service_idx is None:
            continue

        # Reconstruct compose project name: gts-<everything-after-service>
        # e.g., gts-db-main -> gts-main
        # e.g., gts-webapp-612-epic-di -> gts-612-epic-di
        worktree_suffix = "-".join(name_parts[service_idx + 1 :])
        if not worktree_suffix:
            continue
        compose_project = f"gts-{worktree_suffix}"

        # Check if this project is registered
        if compose_project not in registered_projects:
            orphans.append(
                OrphanedContainer(
                    container_id=container_id,
                    container_name=container_name,
                    compose_project=compose_project,
                    service=service,
                    ports=ports.split(", ") if ports else [],
                    status=status,
                )
            )

    return orphans


def get_orphan_ports_in_use() -> dict[int, str]:
    """Get ports currently bound by orphaned GTS containers.

    Returns:
        Dict mapping port number to container name that's using it.
    """
    orphans = find_orphaned_containers()
    ports_in_use = {}

    for orphan in orphans:
        for port_mapping in orphan.ports:
            # Parse port mapping like "127.0.0.1:6381->6379/tcp"
            if "->" in port_mapping:
                host_part = port_mapping.split("->")[0]
                if ":" in host_part:
                    try:
                        port = int(host_part.split(":")[-1])
                        ports_in_use[port] = orphan.container_name
                    except ValueError:
                        pass

    return ports_in_use


def force_cleanup_project(compose_project: str) -> tuple[bool, list[str]]:
    """Force cleanup a compose project by directly removing Docker resources.

    This function uses the Docker CLI directly (not docker compose) to remove
    containers, networks, and volumes for a specific compose project. This is
    useful when docker compose down fails or leaves orphaned resources.

    The cleanup order is:
    1. Stop and remove all containers with the project label
    2. Wait 1 second for network disconnections to propagate
    3. Remove the project network
    4. Remove all project volumes

    Args:
        compose_project: The compose project name (e.g., "gts-345-feature")

    Returns:
        Tuple of (success, list of removed resources)
    """
    removed = []
    all_success = True

    # Step 1: Stop and remove all containers with this project's naming pattern
    try:
        # Find all containers matching the project name
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={compose_project}",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            container_ids = [
                cid.strip() for cid in result.stdout.strip().splitlines() if cid.strip()
            ]
            for container_id in container_ids:
                try:
                    subprocess.run(
                        ["docker", "rm", "-f", container_id],
                        capture_output=True,
                        timeout=30,
                        check=True,
                    )
                    removed.append(f"container:{container_id}")
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    all_success = False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        all_success = False

    # Step 2: Wait for network disconnections to propagate
    # Docker needs time to clean up network attachments after container removal
    time.sleep(1)

    # Step 3: Remove the project network
    network_name = f"{compose_project}_default"
    try:
        subprocess.run(
            ["docker", "network", "rm", network_name],
            capture_output=True,
            timeout=30,
            check=True,
        )
        removed.append(f"network:{network_name}")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # Network might not exist or might have straggler connections
        # Try a second time after another short wait
        time.sleep(0.5)
        try:
            subprocess.run(
                ["docker", "network", "rm", network_name],
                capture_output=True,
                timeout=30,
                check=True,
            )
            removed.append(f"network:{network_name}")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass  # Network may not exist

    # Step 4: Remove all project volumes
    try:
        result = subprocess.run(
            [
                "docker",
                "volume",
                "ls",
                "--filter",
                f"name={compose_project}",
                "--format",
                "{{.Name}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            volume_names = [v.strip() for v in result.stdout.strip().splitlines() if v.strip()]
            for volume_name in volume_names:
                try:
                    subprocess.run(
                        ["docker", "volume", "rm", volume_name],
                        capture_output=True,
                        timeout=30,
                        check=True,
                    )
                    removed.append(f"volume:{volume_name}")
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass  # Volume may be in use
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass

    return all_success, removed


def cleanup_orphaned_containers(dry_run: bool = False) -> list[str]:
    """Stop and remove orphaned GTS containers and their networks/volumes.

    Also cleans up orphaned networks (networks without containers).

    Args:
        dry_run: If True, only report what would be cleaned without doing it.

    Returns:
        List of compose projects/networks that were cleaned up.
    """
    cleaned = []

    # First, handle orphaned containers
    container_orphans = find_orphaned_containers()

    # Group container orphans by compose project
    projects: dict[str, list[OrphanedContainer]] = {}
    for orphan in container_orphans:
        if orphan.compose_project not in projects:
            projects[orphan.compose_project] = []
        projects[orphan.compose_project].append(orphan)

    for project, _containers in projects.items():
        if dry_run:
            cleaned.append(project)
            continue

        # Use force_cleanup_project for robust cleanup
        success, removed = force_cleanup_project(project)
        if success or removed:
            cleaned.append(project)

    # Second, handle orphaned networks (networks without containers)
    # These can remain after containers are stopped but not removed via compose
    network_orphans = find_orphaned_networks()

    for network in network_orphans:
        # Skip if we already cleaned this project's network above
        if network.compose_project in cleaned:
            continue

        if dry_run:
            cleaned.append(f"network:{network.network_name}")
            continue

        # Wait a bit before removing to ensure any container disconnections are processed
        time.sleep(0.5)

        try:
            subprocess.run(
                ["docker", "network", "rm", network.network_id],
                capture_output=True,
                timeout=30,
            )
            cleaned.append(f"network:{network.network_name}")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass  # Network may still have connected containers

    return cleaned
