"""Command modules for worktree CLI.

Each module contains a group of related commands that can be
registered with the main Typer app.
"""

from .auth import register_auth_commands
from .git import register_git_commands
from .info import register_info_commands
from .lifecycle import register_lifecycle_commands
from .maintenance import register_maintenance_commands
from .services import register_services_commands
from .session import register_session_commands
from .setup import register_setup_commands
from .sync import register_sync_commands
from .teardown import register_teardown_commands

__all__ = [
    "register_auth_commands",
    "register_git_commands",
    "register_info_commands",
    "register_lifecycle_commands",
    "register_maintenance_commands",
    "register_services_commands",
    "register_session_commands",
    "register_setup_commands",
    "register_sync_commands",
    "register_teardown_commands",
]
