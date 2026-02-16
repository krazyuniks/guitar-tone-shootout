"""Tests for auth gate in source sync job."""

import json
from pathlib import Path

import pytest


class TestSourceSyncAuthGate:
    def test_auth_gate_raises_when_login_required(self, tmp_path: Path) -> None:
        """_check_auth_gate raises when auth status is not healthy."""
        from worker.jobs.source_sync import _check_auth_gate

        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "login_required"}))

        with pytest.raises(RuntimeError, match="login_required"):
            _check_auth_gate(str(auth_file))

    def test_auth_gate_passes_when_valid(self, tmp_path: Path) -> None:
        from worker.jobs.source_sync import _check_auth_gate

        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "valid"}))

        _check_auth_gate(str(auth_file))  # No exception
