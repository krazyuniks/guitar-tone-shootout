"""Docker Compose operations for worktree management."""

import subprocess
import time
from pathlib import Path

from .config import get_seed_path, settings
from .registry import Worktree


class DockerError(Exception):
    """Docker operation failed."""


def run_compose(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    """Run a docker compose command.

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

    # Docker compose auto-loads .env if present
    cmd = ["docker", "compose", *args]

    # Build environment
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


def start_services(worktree_path: Path, detach: bool = True) -> None:
    """Start all Docker services for a worktree.

    Args:
        worktree_path: Path to the worktree
        detach: Run in background
    """
    args = ["up"]
    if detach:
        args.append("-d")

    run_compose(args, cwd=worktree_path)


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


def remove_volumes(worktree: Worktree, worktree_path: Path) -> None:
    """Remove Docker volumes for a worktree.

    Args:
        worktree: Worktree configuration
        worktree_path: Path to the worktree

    Note:
        Does NOT remove the shared model cache volume.
    """
    # First stop services
    stop_services(worktree_path)

    # Remove volumes
    volumes_to_remove = [
        worktree.volumes.postgres,
        worktree.volumes.redis,
        worktree.volumes.uploads,
    ]

    for volume in volumes_to_remove:
        try:
            subprocess.run(
                ["docker", "volume", "rm", volume],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # Volume may not exist, ignore
            pass


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

    expected_services = {"backend", "frontend", "db", "redis"}
    # worker is optional (uses profile)

    for service in expected_services:
        if service not in status:
            return False
        if status[service] != "running":
            return False

    return True


def wait_for_healthy(
    worktree_path: Path,
    timeout: int | None = None,
    poll_interval: int = 2,
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


def check_backend_health(worktree: Worktree) -> bool:
    """Check if backend health endpoint responds.

    Args:
        worktree: Worktree configuration

    Returns:
        True if backend is healthy
    """
    import urllib.request
    import urllib.error

    url = f"{worktree.backend_url}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def seed_database(worktree_path: Path) -> bool:
    """Seed the database from seed.sql.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if seeding succeeded or no seed file exists
    """
    seed_path = get_seed_path()
    if not seed_path.exists():
        return True

    seed_sql = seed_path.read_text()
    if not seed_sql.strip():
        return True

    try:
        # Pipe seed.sql to psql in the db container
        process = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "shootout",
                "-d",
                "shootout",
            ],
            cwd=worktree_path,
            input=seed_sql,
            capture_output=True,
            text=True,
        )

        return process.returncode == 0
    except (DockerError, subprocess.CalledProcessError):
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
            ["exec", "-T", "backend", "alembic", "upgrade", "head"],
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


def create_shared_volume() -> bool:
    """Create the shared model cache volume if it doesn't exist.

    Returns:
        True if volume exists or was created
    """
    try:
        subprocess.run(
            ["docker", "volume", "create", settings.shared_model_cache_volume],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        # Volume may already exist
        return True


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
