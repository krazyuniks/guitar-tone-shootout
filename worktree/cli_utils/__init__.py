"""CLI module for worktree management.

Provides output utilities, display functions, and other CLI helpers.
"""

from .display import (
    display_github_sync_result,
    display_github_sync_skipped,
    display_issue_analysis,
    display_local_state_report,
    display_orphans_table,
    display_remaining_errors,
    display_stale_branches_table,
    filter_analysis,
)
from .helpers import (
    get_db_password,
    get_public_url,
    get_traefik_subdomain,
    is_traefik_available,
    print_worktree_info,
)
from .output import (
    console,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_warning,
)
from .prompts import (
    display_work_selection,
    prompt_confirm_removal,
    prompt_continue_teardown,
    prompt_start_services,
)

__all__ = [
    # Output utilities
    "console",
    "print_error",
    "print_info",
    "print_panel",
    "print_success",
    "print_warning",
    # Helpers
    "get_db_password",
    "get_public_url",
    "get_traefik_subdomain",
    "is_traefik_available",
    "print_worktree_info",
    # Display functions
    "display_github_sync_result",
    "display_github_sync_skipped",
    "display_issue_analysis",
    "display_local_state_report",
    "display_orphans_table",
    "display_remaining_errors",
    "display_stale_branches_table",
    "filter_analysis",
    # Prompts
    "display_work_selection",
    "prompt_confirm_removal",
    "prompt_continue_teardown",
    "prompt_start_services",
]
