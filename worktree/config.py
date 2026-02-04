"""Configuration and constants for worktree management."""

from pathlib import Path
from typing import NamedTuple

from pydantic import Field
from pydantic_settings import BaseSettings


class PortConfig(NamedTuple):
    """Port configuration for a worktree."""

    nginx: int  # User-facing entry point (routes to backend)
    astro: int  # Astro dev server (internal, build-only)
    backend: int
    db: int
    redis: int
    cloudbeaver: int
    # Observability stack (--profile observability)
    grafana: int
    prometheus: int
    loki: int
    tempo: int
    otlp_grpc: int
    otlp_http: int
    alloy: int


class VolumeConfig(NamedTuple):
    """Volume configuration for a worktree."""

    postgres: str
    redis: str
    uploads: str
    cloudbeaver: str
    # Observability stack (--profile observability)
    grafana: str
    loki: str
    tempo: str
    prometheus: str


class Settings(BaseSettings):
    """Application settings with defaults."""

    # Base ports
    base_port_nginx: int = Field(
        default=9000, description="Base nginx port (user-facing entry point)"
    )
    base_port_astro: int = Field(default=4321, description="Base Astro port (internal, build-only)")
    base_port_backend: int = Field(default=8000, description="Base backend port (internal)")
    base_port_db: int = Field(default=5432, description="Base PostgreSQL port")
    base_port_redis: int = Field(default=6379, description="Base Redis port")
    base_port_cloudbeaver: int = Field(default=8978, description="Base CloudBeaver port")

    # Observability stack base ports
    base_port_grafana: int = Field(default=3000, description="Base Grafana port")
    base_port_prometheus: int = Field(default=9090, description="Base Prometheus port")
    base_port_loki: int = Field(default=3100, description="Base Loki port")
    base_port_tempo: int = Field(default=3200, description="Base Tempo API port")
    base_port_otlp_grpc: int = Field(default=4317, description="Base OTLP gRPC port")
    base_port_otlp_http: int = Field(default=4318, description="Base OTLP HTTP port")
    base_port_alloy: int = Field(default=12345, description="Base Alloy UI port")

    # Port offset multipliers
    offset_multiplier_http: int = Field(
        default=10, description="Multiplier for HTTP ports (astro, backend)"
    )
    offset_multiplier_db: int = Field(
        default=1, description="Multiplier for DB ports (postgres, redis)"
    )

    # Limits
    max_worktrees: int = Field(
        default=256, description="Maximum concurrent worktrees (limited by subnet scheme)"
    )
    warn_worktrees: int = Field(default=5, description="Warn when this many worktrees active")

    # Docker
    compose_project_prefix: str = Field(
        default="gts", description="Prefix for Docker Compose project names"
    )

    # Timeouts
    docker_timeout: int = Field(default=120, description="Docker operation timeout (s)")
    health_timeout: int = Field(default=60, description="Health check timeout (s)")

    class Config:
        env_prefix = "GTS_WORKTREE_"


# Singleton settings instance
settings = Settings()


def get_worktree_root() -> Path:
    """Get the worktree root directory.

    This traverses up from the current worktree to find the parent
    directory containing .worktree/
    """
    current = Path.cwd()

    # Check if we're in a worktree
    while current != current.parent:
        registry_dir = current.parent / ".worktree"
        if registry_dir.is_dir():
            return current.parent
        current = current.parent

    # Fallback: assume standard structure
    # /Work/guitar-tone-shootout-worktrees/main/worktree/config.py
    # -> /Work/guitar-tone-shootout-worktrees/
    module_path = Path(__file__).resolve()
    return module_path.parent.parent.parent.parent


def get_registry_path() -> Path:
    """Get the path to the SQLite registry database."""
    return get_worktree_root() / ".worktree" / "registry.db"


def get_backups_dir() -> Path:
    """Get the path to the database backups directory.

    Returns:
        Path to guitar-tone-shootout-worktrees/backups/
    """
    return get_worktree_root() / "backups"


def get_main_worktree_path() -> Path:
    """Get the path to the main worktree.

    Returns:
        Path to guitar-tone-shootout-worktrees/main/
    """
    return get_worktree_root() / "main"


def get_bare_repo_path() -> Path:
    """Get the path to the bare git repository.

    The bare repo is INSIDE the worktrees folder:
    /Work/guitar-tone-shootout-worktrees/
    ├── guitar-tone-shootout.git/    # Bare repository
    ├── .worktree/                    # Registry
    ├── main/                         # Main worktree
    └── 42-feature/                   # Feature worktrees
    """
    worktree_root = get_worktree_root()
    return worktree_root / "guitar-tone-shootout.git"


def get_current_worktree_path() -> Path:
    """Get the path to the current worktree."""
    return Path.cwd()


def get_current_worktree_name() -> str:
    """Get the name of the current worktree (directory name)."""
    return Path.cwd().name


def calculate_ports(offset: int) -> PortConfig:
    """Calculate port assignments for a given offset.

    Args:
        offset: The worktree offset (0 for main, 1+ for features)

    Returns:
        PortConfig with all service ports including observability stack
    """
    http_offset = offset * settings.offset_multiplier_http
    db_offset = offset * settings.offset_multiplier_db

    return PortConfig(
        nginx=settings.base_port_nginx + http_offset,  # User-facing entry point
        astro=settings.base_port_astro + http_offset,  # Internal (Astro dev server, build-only)
        backend=settings.base_port_backend + http_offset,  # Internal (FastAPI)
        db=settings.base_port_db + db_offset,
        redis=settings.base_port_redis + db_offset,
        cloudbeaver=settings.base_port_cloudbeaver + http_offset,
        # Observability stack ports (use http offset for all web UIs)
        grafana=settings.base_port_grafana + http_offset,
        prometheus=settings.base_port_prometheus + http_offset,
        loki=settings.base_port_loki + http_offset,
        tempo=settings.base_port_tempo + http_offset,
        otlp_grpc=settings.base_port_otlp_grpc + http_offset,
        otlp_http=settings.base_port_otlp_http + http_offset,
        alloy=settings.base_port_alloy + http_offset,
    )


def calculate_volumes(worktree_name: str) -> VolumeConfig:
    """Calculate volume names for a worktree.

    Args:
        worktree_name: The worktree name (e.g., "main", "42-feature-audio")

    Returns:
        VolumeConfig with all volume names including observability stack
    """
    prefix = settings.compose_project_prefix
    # Sanitize name for Docker volume naming
    safe_name = worktree_name.replace("/", "-").lower()

    return VolumeConfig(
        postgres=f"{prefix}-{safe_name}-postgres",
        redis=f"{prefix}-{safe_name}-redis",
        uploads=f"{prefix}-{safe_name}-uploads",
        cloudbeaver=f"{prefix}-{safe_name}-cloudbeaver",
        # Observability stack volumes
        grafana=f"{prefix}-{safe_name}-grafana",
        loki=f"{prefix}-{safe_name}-loki",
        tempo=f"{prefix}-{safe_name}-tempo",
        prometheus=f"{prefix}-{safe_name}-prometheus",
    )


def get_compose_project_name(worktree_name: str) -> str:
    """Get the Docker Compose project name for a worktree.

    Args:
        worktree_name: The worktree name

    Returns:
        Docker Compose project name
    """
    prefix = settings.compose_project_prefix
    # Sanitize and truncate for Docker naming limits
    safe_name = worktree_name.replace("/", "-").lower()[:20]
    return f"{prefix}-{safe_name}"
