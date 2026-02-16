"""Tests for auth gate function."""

import json
from pathlib import Path

from core.domain.auth_gate import check_auth_status
from core.domain.value_objects.source_auth_status import SourceAuthStatus


class TestCheckAuthStatus:
    def test_returns_unknown_when_file_missing(self, tmp_path: Path) -> None:
        result = check_auth_status(str(tmp_path / "nonexistent.json"))
        assert result == SourceAuthStatus.UNKNOWN

    def test_returns_unknown_when_file_not_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        result = check_auth_status(str(bad_file))
        assert result == SourceAuthStatus.UNKNOWN

    def test_returns_status_from_file(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "valid"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.VALID

    def test_returns_login_required(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "login_required"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.LOGIN_REQUIRED

    def test_returns_valid_when_status_missing_but_token_exists(self, tmp_path: Path) -> None:
        """Backwards-compat: pre-existing auth files without auth_status field."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"access_token": "encrypted"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.VALID

    def test_returns_unknown_when_no_status_and_no_token(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"username": "test"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.UNKNOWN

    def test_returns_unknown_for_unrecognised_status(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "bogus_value"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.UNKNOWN
