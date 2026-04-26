"""Resource availability and display helpers for worktree commands."""

from .config import PortConfig, VolumeConfig


def check_ports_available(ports: PortConfig) -> dict[str, bool]:
    """Check if ports are available for binding.

    Args:
        ports: PortConfig to check

    Returns:
        Dict mapping port names to availability (True = available)
    """
    import socket

    results = {}

    # Core services (frontend not exposed - Docker internal only)
    core_ports = [
        ("nginx", ports.nginx),  # User-facing entry point
        ("webapp", ports.webapp),
        ("db", ports.db),
        ("redis", ports.redis),
        ("cloudbeaver", ports.cloudbeaver),
        ("video", ports.video),
    ]

    # Observability services (optional, profile-based)
    observability_ports = [
        ("grafana", ports.grafana),
        ("prometheus", ports.prometheus),
        ("loki", ports.loki),
        ("tempo", ports.tempo),
        ("otlp_grpc", ports.otlp_grpc),
        ("otlp_http", ports.otlp_http),
        ("alloy", ports.alloy),
    ]

    for name, port in core_ports + observability_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                results[name] = True
        except OSError:
            results[name] = False

    return results


def format_ports_display(ports: PortConfig) -> str:
    """Format ports for display.

    Returns:
        Formatted string like "nginx:9000/wa:8000/db:5432/redis:6379/cb:8978/vid:8002"
    """
    return (
        f"nginx:{ports.nginx}/wa:{ports.webapp}/"
        f"db:{ports.db}/redis:{ports.redis}/cb:{ports.cloudbeaver}/vid:{ports.video}"
    )


def format_volumes_display(volumes: VolumeConfig) -> str:
    """Format volumes for display."""
    return (
        f"pg:{volumes.postgres}, redis:{volumes.redis}, "
        f"storage:../gts-storage/ (bind), cb:{volumes.cloudbeaver}"
    )
