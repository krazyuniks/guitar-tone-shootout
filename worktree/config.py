"""Configuration and constants for worktree management."""

from pathlib import Path
from typing import NamedTuple

from pydantic import Field
from pydantic_settings import BaseSettings


class PortConfig(NamedTuple):
    """Port configuration for a worktree."""

    frontend: int
    backend: int
    db: int
    redis: int
    cloudbeaver: int


class VolumeConfig(NamedTuple):
    """Volume configuration for a worktree."""

    postgres: str
    redis: str
    uploads: str
    cloudbeaver: str


class Settings(BaseSettings):
    """Application settings with defaults."""

    # Base ports
    base_port_frontend: int = Field(default=4321, description="Base frontend port")
    base_port_backend: int = Field(default=8000, description="Base backend port")
    base_port_db: int = Field(default=5432, description="Base PostgreSQL port")
    base_port_redis: int = Field(default=6379, description="Base Redis port")
    base_port_cloudbeaver: int = Field(default=8978, description="Base CloudBeaver port")

    # Port offset multipliers
    offset_multiplier_http: int = Field(
        default=10, description="Multiplier for HTTP ports (frontend, backend)"
    )
    offset_multiplier_db: int = Field(
        default=1, description="Multiplier for DB ports (postgres, redis)"
    )

    # Limits
    max_worktrees: int = Field(default=10, description="Maximum concurrent worktrees")
    warn_worktrees: int = Field(
        default=5, description="Warn when this many worktrees active"
    )

    # Docker
    compose_project_prefix: str = Field(
        default="gts", description="Prefix for Docker Compose project names"
    )
    shared_model_cache_volume: str = Field(
        default="gts-model-cache", description="Shared model cache volume name"
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


def get_seed_path() -> Path:
    """Get the path to the shared seed.sql file."""
    return get_worktree_root() / "seed.sql"


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
        PortConfig with frontend, backend, db, redis, cloudbeaver ports
    """
    return PortConfig(
        frontend=settings.base_port_frontend
        + (offset * settings.offset_multiplier_http),
        backend=settings.base_port_backend + (offset * settings.offset_multiplier_http),
        db=settings.base_port_db + (offset * settings.offset_multiplier_db),
        redis=settings.base_port_redis + (offset * settings.offset_multiplier_db),
        cloudbeaver=settings.base_port_cloudbeaver
        + (offset * settings.offset_multiplier_http),
    )


def calculate_volumes(worktree_name: str) -> VolumeConfig:
    """Calculate volume names for a worktree.

    Args:
        worktree_name: The worktree name (e.g., "main", "42-feature-audio")

    Returns:
        VolumeConfig with postgres, redis, uploads, cloudbeaver volume names
    """
    prefix = settings.compose_project_prefix
    # Sanitize name for Docker volume naming
    safe_name = worktree_name.replace("/", "-").lower()

    return VolumeConfig(
        postgres=f"{prefix}-{safe_name}-postgres",
        redis=f"{prefix}-{safe_name}-redis",
        uploads=f"{prefix}-{safe_name}-uploads",
        cloudbeaver=f"{prefix}-{safe_name}-cloudbeaver",
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
