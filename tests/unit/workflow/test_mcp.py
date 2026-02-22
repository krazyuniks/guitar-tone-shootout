"""Tests for MCP server configuration resolution."""

import json

from workflow.mcp import build_mcp_config, read_all_servers


class TestBuildMcpConfig:
    """build_mcp_config() returns valid --mcp-config JSON."""

    def test_empty_list_returns_empty_servers(self):
        """Empty server list produces empty mcpServers."""
        result = build_mcp_config([])
        parsed = json.loads(result)
        assert parsed == {"mcpServers": {}}

    def test_unknown_server_raises(self):
        """Requesting a non-existent server raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="Unknown MCP server"):
            build_mcp_config(["nonexistent-server-xyz"])


class TestReadAllServers:
    """read_all_servers() reads from Claude config files."""

    def test_returns_dict(self):
        """Always returns a dict (possibly empty)."""
        result = read_all_servers()
        assert isinstance(result, dict)
