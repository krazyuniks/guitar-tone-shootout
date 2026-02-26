"""Tests for scheduled token refresh task."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet


def _make_auth_file(tmp_path: Path, fernet: Fernet, **overrides) -> Path:
    auth_file = tmp_path / ".gts-auth.json"
    expires_at = overrides.pop(
        "expires_at",
        (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    data = {
        "access_token": fernet.encrypt(b"test-access").decode(),
        "refresh_token": fernet.encrypt(b"test-refresh").decode(),
        "expires_at": expires_at,
        "auth_status": "valid",
        "saved_at": datetime.now(UTC).isoformat(),
        "user_id": "test-user",
        **overrides,
    }
    auth_file.write_text(json.dumps(data))
    return auth_file


class TestRefreshTokenTask:
    async def test_skips_when_login_required(self, tmp_path: Path) -> None:
        """Task does nothing when auth_status is login_required."""
        from t3k_sync.tasks import refresh_t3k_token

        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(tmp_path, fernet, auth_status="login_required")

        await refresh_t3k_token(
            auth_file_path=str(auth_file),
            encryption_key=key.decode(),
        )

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "login_required"  # unchanged

    async def test_skips_when_token_not_expiring(self, tmp_path: Path) -> None:
        """Task does nothing when token expires in >10 minutes."""
        from t3k_sync.tasks import refresh_t3k_token

        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(tmp_path, fernet)  # 1hr expiry

        await refresh_t3k_token(
            auth_file_path=str(auth_file),
            encryption_key=key.decode(),
        )

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "valid"  # unchanged, no refresh

    async def test_skips_when_file_missing(self) -> None:
        """Task does nothing when auth file doesn't exist."""
        from t3k_sync.tasks import refresh_t3k_token

        await refresh_t3k_token(
            auth_file_path="/nonexistent/path/auth.json",
            encryption_key="fake-key",
        )
        # No exception raised — just logs and returns
