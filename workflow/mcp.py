"""MCP server configuration resolution for agent dispatch.

Reads MCP server definitions from Claude Code's configuration files
(same sources as the ``cld`` wrapper) and builds ``--mcp-config`` JSON
for ``dispatch_agent()``.

Configuration sources (merged in order, last wins):
    1. ``~/.claude.json``
    2. ``~/.claude/settings.json``
    3. ``~/.claude/settings.local.json``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATHS = [
    Path.home() / ".claude.json",
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.local.json",
]


def read_all_servers() -> dict[str, dict]:
    """Read all MCP server definitions from Claude Code config files.

    Merges ``mcpServers`` from each config file in order (last wins).

    Returns:
        Dict mapping server name to its full configuration dict.
    """
    merged: dict[str, dict] = {}
    for path in _CONFIG_PATHS:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            continue
        servers = data.get("mcpServers", {})
        if isinstance(servers, dict):
            merged.update(servers)
    return merged


def build_mcp_config(server_names: list[str]) -> str:
    """Build a ``--mcp-config`` JSON string for the given server names.

    Args:
        server_names: List of MCP server names to include.
            Empty list produces ``{"mcpServers": {}}``.

    Returns:
        JSON string suitable for ``--mcp-config``.

    Raises:
        ValueError: If any server name is not found in the merged config.
    """
    if not server_names:
        return '{"mcpServers":{}}'

    all_servers = read_all_servers()
    selected: dict[str, dict] = {}
    missing = [name for name in server_names if name not in all_servers]
    if missing:
        raise ValueError(
            f"Unknown MCP server(s): {missing}. Available: {sorted(all_servers.keys())}"
        )
    for name in server_names:
        selected[name] = all_servers[name]
    return json.dumps({"mcpServers": selected})
