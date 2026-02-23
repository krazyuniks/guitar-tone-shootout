"""CLI helper functions for worktree commands.

Provides shared utilities used across multiple command modules.
"""

import platform
from pathlib import Path

from rich.panel import Panel

from ..health import check_worktree_health
from .output import console


def is_traefik_available() -> bool:
    """Check if Traefik is available for this environment.

    Traefik is considered available when:
    - Running on Linux (server deployment)
    - Traefik container is running

    Returns:
        True if Traefik routing is available.
    """
    if platform.system() != "Linux":
        return False

    # Check if Traefik container is running
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=traefik"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_traefik_subdomain(branch: str) -> str:
    """Derive Traefik subdomain from branch name.

    Args:
        branch: Git branch name (e.g., "main", "526/epic-...")

    Returns:
        Subdomain string (e.g., "main", "526", "feature-foo")
    """
    # main branch gets "main" subdomain
    if branch == "main":
        return "main"

    # Issue branches (e.g., "526/epic-..." or "42-fix-bug") get issue number
    # Check for "N/..." pattern
    if "/" in branch:
        prefix = branch.split("/")[0]
        if prefix.isdigit():
            return prefix

    # Check for "N-..." pattern at start
    if "-" in branch:
        prefix = branch.split("-")[0]
        if prefix.isdigit():
            return prefix

    # Fallback: sanitize branch name for subdomain (max 20 chars, alphanumeric + hyphen)
    sanitized = "".join(c if c.isalnum() or c == "-" else "-" for c in branch.lower())
    sanitized = sanitized.strip("-")[:20].rstrip("-")
    return sanitized or "main"


def get_public_url(branch: str) -> str | None:
    """Get the public Traefik URL for a worktree.

    Args:
        branch: Git branch name

    Returns:
        Public URL (e.g., "https://526.tone-shootout.com") or None if not available.
    """
    if not is_traefik_available():
        return None

    subdomain = get_traefik_subdomain(branch)
    return f"https://{subdomain}.tone-shootout.com"


def get_db_password(worktree_path: Path) -> str:
    """Read DB_PASSWORD from .env file.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        The database password, or "devpassword" as default.
    """
    db_password = "devpassword"  # default
    env_file = worktree_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DB_PASSWORD="):
                db_password = line.split("=", 1)[1].strip()
                break
    return db_password


def print_worktree_info(worktree, health_result=None, show_services: bool = True) -> None:
    """Print detailed worktree information including containers and credentials.

    Args:
        worktree: WorktreeInfo object with worktree details.
        health_result: Optional HealthResult from check_worktree_health.
        show_services: Whether to show container status (default True).
    """
    wt_path = Path(worktree.worktree_path)
    db_password = get_db_password(wt_path)

    # Get health if not provided
    if health_result is None and wt_path.exists():
        health_result = check_worktree_health(wt_path)

    status_str = (
        "[green]Healthy[/green]"
        if (health_result and health_result.healthy)
        else "[yellow]Unknown[/yellow]"
    )
    if health_result and not health_result.healthy:
        status_str = "[red]Unhealthy[/red]"

    # Check for public URL (Traefik on Linux servers)
    public_url = get_public_url(worktree.branch)
    public_url_line = ""
    if public_url:
        public_url_line = f"\n  [bold green]Public:[/bold green]     {public_url}"

    content = f"""[bold]Worktree:[/bold] {worktree.worktree_name}
[bold]Branch:[/bold] {worktree.branch}
[bold]Path:[/bold] {worktree.worktree_path}
[bold]Status:[/bold] {status_str}

[bold cyan]Service URLs:[/bold cyan]{public_url_line}
  App (nginx): http://localhost:{worktree.ports.nginx}
  Astro:       http://localhost:{worktree.ports.astro} (build-only)
  Webapp:      http://localhost:{worktree.ports.webapp}
  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}

[bold cyan]Database Access:[/bold cyan]
  Host: localhost:{worktree.ports.db}
  User: gts
  Pass: {db_password}
  DB:   gts_core

[bold cyan]CloudBeaver Login:[/bold cyan]
  User: cbadmin
  Pass: {db_password}

[bold]Ports:[/bold]
  Nginx:       {worktree.ports.nginx}
  Astro:       {worktree.ports.astro} (build-only)
  Webapp:      {worktree.ports.webapp}
  Database:    {worktree.ports.db}
  CloudBeaver: {worktree.ports.cloudbeaver}"""

    # Only show Redis and Observability for main worktree (jobs profile)
    is_main = worktree.branch == "main"
    if is_main:
        content += f"""

[bold]Jobs Profile (main only):[/bold]
  Redis:       {worktree.ports.redis}

[bold cyan]Observability (--profile observability):[/bold cyan]
  Grafana:     http://localhost:{worktree.ports.grafana}
  Prometheus:  http://localhost:{worktree.ports.prometheus}
  Loki:        http://localhost:{worktree.ports.loki}
  Tempo:       http://localhost:{worktree.ports.tempo}
  Alloy:       http://localhost:{worktree.ports.alloy}"""

    if show_services and health_result:
        content += "\n\n[bold]Containers:[/bold]"
        for svc, state in health_result.services.items():
            icon = "[green]●[/green]" if state == "running" else "[red]○[/red]"
            content += f"\n  {icon} {svc}: {state}"

        if health_result.issues:
            content += "\n\n[bold]Issues:[/bold]"
            for issue in health_result.issues:
                content += f"\n  - {issue}"

    console.print(Panel(content, title=f"Worktree: {worktree.worktree_name}"))
