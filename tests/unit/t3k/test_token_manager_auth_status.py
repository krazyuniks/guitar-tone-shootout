"""Tests for token manager auth_status field updates."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

from source_t3k.adapters.inbound.token_manager import T3KTokenManager


def _make_auth_file(tmp_path: Path, fernet: Fernet, **overrides) -> Path:
    """Create a test auth file with encrypted tokens."""
    auth_file = tmp_path / ".gts-auth.json"
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    data = {
        "access_token": fernet.encrypt(b"test-access").decode(),
        "refresh_token": fernet.encrypt(b"test-refresh").decode(),
        "expires_at": expires_at,
        "user_id": "test-user",
        **overrides,
    }
    auth_file.write_text(json.dumps(data))
    return auth_file


class TestTokenManagerAuthStatus:
    def test_load_sets_auth_status_valid(self, tmp_path: Path) -> None:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(tmp_path, fernet)

        manager = T3KTokenManager(
            auth_file_path=str(auth_file),
            base_url="https://example.com",
            encryption_key=key.decode(),
        )
        manager._load_from_auth_file()

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "valid"

    def test_save_sets_auth_status_valid(self, tmp_path: Path) -> None:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(tmp_path, fernet, auth_status="expiring_soon")

        manager = T3KTokenManager(
            auth_file_path=str(auth_file),
            base_url="https://example.com",
            encryption_key=key.decode(),
        )
        manager._save_to_auth_file("new-access", "new-refresh", 3600)

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "valid"
