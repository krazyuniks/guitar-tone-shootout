# T3K Login & Auto-Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add official T3K login CLI, proactive token refresh, and auth gate that prevents any T3K API call when auth is unhealthy.

**Architecture:** `SourceAuthStatus` enum in core, `check_auth_status()` gate function in source_t3k, scheduled refresh job in scheduler, login CLI on host. Auth file is single source of truth — all components read plaintext `auth_status` field before doing any work.

**Tech Stack:** Python 3.11+, cryptography (Fernet), httpx, Chromium CDP, TaskIQ scheduler, FastAPI admin API.

**Design doc:** `docs/plans/2026-02-16-t3k-login-auto-refresh-design.md`

---

### Task 1: SourceAuthStatus enum

**Files:**
- Create: `libs/core/src/core/domain/value_objects/source_auth_status.py`
- Modify: `libs/core/src/core/domain/value_objects/__init__.py` (if it exists, export new enum)
- Test: `tests/unit/backend/core/value_objects/test_source_auth_status.py`

**Step 1: Write the test**

```python
"""Tests for SourceAuthStatus value object."""

import pytest

from core.domain.value_objects.source_auth_status import SourceAuthStatus


class TestSourceAuthStatus:
    def test_all_values_are_lowercase_strings(self) -> None:
        for member in SourceAuthStatus:
            assert member.value == member.value.lower()
            assert isinstance(member.value, str)

    def test_can_proceed_returns_true_for_valid(self) -> None:
        assert SourceAuthStatus.VALID.can_proceed() is True

    def test_can_proceed_returns_true_for_expiring_soon(self) -> None:
        assert SourceAuthStatus.EXPIRING_SOON.can_proceed() is True

    def test_can_proceed_returns_false_for_refresh_failed(self) -> None:
        assert SourceAuthStatus.REFRESH_FAILED.can_proceed() is False

    def test_can_proceed_returns_false_for_login_required(self) -> None:
        assert SourceAuthStatus.LOGIN_REQUIRED.can_proceed() is False

    def test_can_proceed_returns_false_for_unknown(self) -> None:
        assert SourceAuthStatus.UNKNOWN.can_proceed() is False

    def test_from_string_valid_value(self) -> None:
        assert SourceAuthStatus("valid") == SourceAuthStatus.VALID

    def test_from_string_unknown_value_raises(self) -> None:
        with pytest.raises(ValueError):
            SourceAuthStatus("bogus")

    def test_needs_login_true_for_login_required(self) -> None:
        assert SourceAuthStatus.LOGIN_REQUIRED.needs_login() is True

    def test_needs_login_false_for_valid(self) -> None:
        assert SourceAuthStatus.VALID.needs_login() is False
```

**Step 2: Run test to verify it fails**

Run: `just tdd tests/unit/backend/core/value_objects/test_source_auth_status.py`
Expected: FAIL — module not found

**Step 3: Write the enum**

```python
"""Source authentication status value object.

Tracks whether a source's OAuth tokens are healthy enough to make API calls.
Stored as plaintext in .gts-auth.json so any component can read it without decryption.
"""

from enum import Enum


class SourceAuthStatus(str, Enum):
    """Authentication health of a source's OAuth tokens.

    Written by the scheduler refresh job. Read by sync jobs and admin API
    as a preflight gate — no API calls proceed unless status is VALID or
    EXPIRING_SOON.
    """

    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    REFRESH_FAILED = "refresh_failed"
    LOGIN_REQUIRED = "login_required"
    UNKNOWN = "unknown"

    def can_proceed(self) -> bool:
        """Return True if API calls are safe to make."""
        return self in (SourceAuthStatus.VALID, SourceAuthStatus.EXPIRING_SOON)

    def needs_login(self) -> bool:
        """Return True if manual re-authentication is needed."""
        return self == SourceAuthStatus.LOGIN_REQUIRED
```

**Step 4: Run test to verify it passes**

Run: `just tdd tests/unit/backend/core/value_objects/test_source_auth_status.py`
Expected: PASS

**Step 5: Commit**

```
git add libs/core/src/core/domain/value_objects/source_auth_status.py tests/unit/backend/core/value_objects/test_source_auth_status.py
git commit -m "feat(core): add SourceAuthStatus value object"
```

---

### Task 2: Auth gate function (check_auth_status)

**Files:**
- Create: `libs/core/src/core/domain/auth_gate.py`
- Test: `tests/unit/backend/core/test_auth_gate.py`

The gate lives in core (not source_t3k) because multiple apps need it: scheduler, worker, admin API. It reads plaintext JSON only — no decryption, no imports from source_t3k.

**Step 1: Write the test**

```python
"""Tests for auth gate function."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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

    def test_returns_unknown_when_status_field_missing(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"access_token": "encrypted"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.UNKNOWN

    def test_returns_unknown_for_unrecognised_status(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_status": "bogus_value"}))
        result = check_auth_status(str(auth_file))
        assert result == SourceAuthStatus.UNKNOWN
```

**Step 2: Run test to verify it fails**

Run: `just tdd tests/unit/backend/core/test_auth_gate.py`
Expected: FAIL — module not found

**Step 3: Write the gate function**

```python
"""Auth gate — preflight check before any source API call.

Reads plaintext auth_status from .gts-auth.json. No decryption, no network.
"""

import json
import logging
from pathlib import Path

from core.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)


def check_auth_status(auth_file_path: str) -> SourceAuthStatus:
    """Read auth_status from auth file. No decryption, no API calls.

    Returns SourceAuthStatus.UNKNOWN if the file is missing, unreadable,
    or doesn't contain a recognised auth_status value.
    """
    path = Path(auth_file_path)
    if not path.exists():
        logger.debug("Auth file not found: %s", auth_file_path)
        return SourceAuthStatus.UNKNOWN

    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Auth file unreadable: %s", auth_file_path)
        return SourceAuthStatus.UNKNOWN

    raw_status = data.get("auth_status")
    if raw_status is None:
        return SourceAuthStatus.UNKNOWN

    try:
        return SourceAuthStatus(raw_status)
    except ValueError:
        logger.warning("Unrecognised auth_status in %s: %s", auth_file_path, raw_status)
        return SourceAuthStatus.UNKNOWN
```

**Step 4: Run test to verify it passes**

Run: `just tdd tests/unit/backend/core/test_auth_gate.py`
Expected: PASS

**Step 5: Commit**

```
git add libs/core/src/core/domain/auth_gate.py tests/unit/backend/core/test_auth_gate.py
git commit -m "feat(core): add check_auth_status gate function"
```

---

### Task 3: Token manager writes auth_status field

**Files:**
- Modify: `sources/t3k/src/source_t3k/adapters/inbound/token_manager.py`
- Test: `tests/unit/t3k/test_token_manager_auth_status.py`

The token manager already writes to the auth file on refresh. Add `auth_status` field updates at each lifecycle point:
- `_load_from_auth_file()` success → write `valid` if not already set
- `_save_to_auth_file()` after successful refresh → write `valid`
- `_refresh()` on 401 → write `login_required`
- `_refresh()` on other error → write `refresh_failed`

**Step 1: Write the test**

```python
"""Tests for token manager auth_status field updates."""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet

from core.domain.value_objects.source_auth_status import SourceAuthStatus
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
```

**Step 2: Run test to verify it fails**

Run: `just tdd tests/unit/t3k/test_token_manager_auth_status.py`
Expected: FAIL — auth_status not in file

**Step 3: Update token_manager.py**

In `_load_from_auth_file()`, after the successful load (before `logger.info`), add:
```python
self._update_auth_status_field(SourceAuthStatus.VALID)
```

In `_save_to_auth_file()`, add `auth_status` to the data written:
```python
existing["auth_status"] = SourceAuthStatus.VALID.value
```

In `_refresh()`, wrap the error cases:
- After `if response.status_code == 401:` add:
  ```python
  self._update_auth_status_field(SourceAuthStatus.LOGIN_REQUIRED)
  ```
- Add a try/except around the main refresh logic; on non-401 exceptions:
  ```python
  self._update_auth_status_field(SourceAuthStatus.REFRESH_FAILED)
  ```

Add helper method:
```python
def _update_auth_status_field(self, status: SourceAuthStatus) -> None:
    """Update only the auth_status field in the auth file."""
    path = Path(self._auth_file_path)
    if not path.exists():
        return
    try:
        with open(path) as f:
            data = json.load(f)
        data["auth_status"] = status.value
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except (json.JSONDecodeError, OSError):
        pass  # Best-effort — don't crash on status update failure
```

Import at top of file:
```python
from core.domain.value_objects.source_auth_status import SourceAuthStatus
```

**Step 4: Run test to verify it passes**

Run: `just tdd tests/unit/t3k/test_token_manager_auth_status.py`
Expected: PASS

**Step 5: Commit**

```
git add sources/t3k/src/source_t3k/adapters/inbound/token_manager.py tests/unit/t3k/test_token_manager_auth_status.py
git commit -m "feat(t3k): token manager writes auth_status to auth file"
```

---

### Task 4: Infra — scheduler gets auth file access

**Files:**
- Modify: `docker-compose.yml` (scheduler service, lines 180-209)
- Modify: `worktree/templates/docker-compose.override.yml.j2` (scheduler section, lines 60-64)

No test for this — infrastructure config.

**Step 1: Update base docker-compose.yml scheduler service**

Add to scheduler `environment:` block:
```yaml
      OAUTH_ENCRYPTION_KEY: ${OAUTH_ENCRYPTION_KEY}
```

Add to scheduler `volumes:`:
```yaml
      - ./sources:/app/sources:ro
```

**Step 2: Update override template**

Replace scheduler section in `worktree/templates/docker-compose.override.yml.j2`:
```yaml
  scheduler:
    container_name: {{ worktree.compose_project }}-scheduler
    volumes:
      - ./libs:/app/libs:ro
      - ./apps/scheduler:/app/apps/scheduler
      - ./sources:/app/sources:ro
      # Parent dir for shared auth file (.gts-auth.json)
      - ../:/worktrees
    environment:
      - GTS_AUTH_FILE=/worktrees/.gts-auth.json
```

**Step 3: Regenerate override and restart**

```bash
./worktree.py setup main
just restart scheduler
```

**Step 4: Commit**

```
git add docker-compose.yml worktree/templates/docker-compose.override.yml.j2
git commit -m "infra(scheduler): add auth file mount and encryption key"
```

---

### Task 5: Fix scheduler crash-loop (remove webapp import)

**Files:**
- Modify: `apps/scheduler/src/scheduler/schedules/jobs.py`

The scheduler imports `webapp.adapters.persistence.models.job.Job` (line 21) and `worker.jobs.source_sync.handle_source_sync` (line 22). Both violate dependency rules. The scheduler should only depend on core.

**Step 1: Analyse what the imports are used for**

- `Job` (JobModel) — used in `monitor_stale_jobs` and `process_pending_retries` to query/update job rows
- `handle_source_sync` — used in `ensure_source_sync_running` to dispatch via `.kiq()`

**Step 2: Replace Job model import with raw SQL**

The scheduler only does simple UPDATE/SELECT on the jobs table. Replace `JobModel` usage with `sqlalchemy.text()` queries. This removes the webapp dependency entirely.

For `monitor_stale_jobs`:
```python
stmt = text("""
    UPDATE jobs SET status = :dead_status, error = :error, completed_at = :now
    WHERE status = :running_status AND last_heartbeat < :threshold
""")
await session.execute(stmt, {
    "dead_status": JobStatus.DEAD_LETTERED.value,
    "error": "Stale heartbeat: worker failed to update within 2 minutes",
    "running_status": JobStatus.RUNNING.value,
    "threshold": stale_threshold,
    "now": datetime.now(UTC),
})
```

For `process_pending_retries`:
```python
stmt = text("""
    UPDATE jobs SET status = :pending_status
    WHERE status = :failed_status
      AND next_retry_at IS NOT NULL
      AND next_retry_at <= :now
      AND attempt < max_attempts
""")
await session.execute(stmt, {
    "pending_status": JobStatus.PENDING.value,
    "failed_status": JobStatus.FAILED.value,
    "now": now,
})
```

For `ensure_source_sync_running` — replace `handle_source_sync.kiq()` with direct Redis LPUSH to the TaskIQ queue, OR remove this function entirely and rely on the admin API `POST /api/admin/sources/t3k/sync` being called manually/from a different path. The simplest fix: use `httpx` to call the worker admin endpoint instead of importing worker code.

```python
async with httpx.AsyncClient() as client:
    await client.post("http://worker:8001/api/admin/sources/t3k/sync")
```

Remove imports: `webapp.adapters.persistence.models.job`, `worker.jobs.source_sync`

**Step 3: Run scheduler tests**

Run: `just tdd tests/unit/scheduler/` (if tests exist) or verify scheduler starts without crash:
```bash
docker compose logs scheduler --tail 20
```

**Step 4: Commit**

```
git add apps/scheduler/src/scheduler/schedules/jobs.py
git commit -m "fix(scheduler): remove webapp/worker imports, use raw SQL + admin API"
```

---

### Task 6: Scheduled refresh job

**Files:**
- Create: `apps/scheduler/src/scheduler/schedules/auth.py`
- Modify: `apps/scheduler/src/scheduler/main.py` (import new module)
- Test: `tests/unit/scheduler/test_auth_refresh_job.py`

**Step 1: Write the test**

```python
"""Tests for scheduled token refresh job."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from core.domain.value_objects.source_auth_status import SourceAuthStatus


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


class TestRefreshTokenJob:
    def test_skips_when_login_required(self, tmp_path: Path) -> None:
        """Job does nothing when auth_status is login_required."""
        from scheduler.schedules.auth import refresh_t3k_token

        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(
            tmp_path, fernet, auth_status="login_required"
        )

        import asyncio
        asyncio.run(refresh_t3k_token(
            auth_file_path=str(auth_file),
            encryption_key=key.decode(),
        ))

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "login_required"  # unchanged

    def test_skips_when_token_not_expiring(self, tmp_path: Path) -> None:
        """Job does nothing when token expires in >10 minutes."""
        from scheduler.schedules.auth import refresh_t3k_token

        key = Fernet.generate_key()
        fernet = Fernet(key)
        auth_file = _make_auth_file(tmp_path, fernet)  # 1hr expiry

        import asyncio
        asyncio.run(refresh_t3k_token(
            auth_file_path=str(auth_file),
            encryption_key=key.decode(),
        ))

        data = json.loads(auth_file.read_text())
        assert data["auth_status"] == "valid"  # unchanged, no refresh

    def test_skips_when_file_missing(self) -> None:
        """Job does nothing when auth file doesn't exist."""
        from scheduler.schedules.auth import refresh_t3k_token

        import asyncio
        asyncio.run(refresh_t3k_token(
            auth_file_path="/nonexistent/path/auth.json",
            encryption_key="fake-key",
        ))
        # No exception raised — just logs and returns
```

**Step 2: Run test to verify it fails**

Run: `just tdd tests/unit/scheduler/test_auth_refresh_job.py`
Expected: FAIL — module not found

**Step 3: Write the refresh job**

Create `apps/scheduler/src/scheduler/schedules/auth.py`:

```python
"""Scheduled T3K token refresh.

Runs every 5 minutes. Checks auth file expiry, refreshes proactively.
Conservative: no retry loops, no API calls when auth is unhealthy.
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.domain.auth_gate import check_auth_status
from core.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)

# Refresh when token expires within this window
_REFRESH_WINDOW_SECONDS = 600  # 10 minutes

# Fallback refresh interval when no expires_at in auth file
_FALLBACK_REFRESH_SECONDS = 1800  # 30 minutes

# Track file mtime to detect manual re-login after LOGIN_REQUIRED
_last_login_required_mtime: float = 0.0


def _update_auth_status(auth_file_path: str, status: SourceAuthStatus) -> None:
    """Update auth_status field in auth file. Best-effort."""
    path = Path(auth_file_path)
    try:
        with open(path) as f:
            data = json.load(f)
        data["auth_status"] = status.value
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except (json.JSONDecodeError, OSError):
        pass


async def refresh_t3k_token(
    auth_file_path: str | None = None,
    encryption_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Check token expiry and refresh if needed.

    Args:
        auth_file_path: Override for testing (default: GTS_AUTH_FILE env)
        encryption_key: Override for testing (default: OAUTH_ENCRYPTION_KEY env)
        base_url: Override for testing (default: T3K_API_URL env)
    """
    global _last_login_required_mtime

    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    if encryption_key is None:
        encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if base_url is None:
        base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")

    path = Path(auth_file_path)
    if not path.exists():
        logger.debug("Auth file not found: %s", auth_file_path)
        return

    # Check auth gate
    status = check_auth_status(auth_file_path)
    if status == SourceAuthStatus.LOGIN_REQUIRED:
        # Only retry if file was modified (user ran just t3k-login)
        current_mtime = path.stat().st_mtime
        if current_mtime <= _last_login_required_mtime:
            logger.debug("Auth login_required, file unchanged — skipping")
            return
        # File was modified — re-check
        logger.info("Auth file modified after login_required — re-checking")

    # Read expiry info
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    expires_at_str = data.get("expires_at")
    saved_at_str = data.get("saved_at")
    now = datetime.now(UTC)

    needs_refresh = False

    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        seconds_until_expiry = (expires_at - now).total_seconds()

        if seconds_until_expiry > _REFRESH_WINDOW_SECONDS:
            # Token is fine — ensure status is VALID
            if status != SourceAuthStatus.VALID:
                _update_auth_status(auth_file_path, SourceAuthStatus.VALID)
            return

        logger.info(
            "Token expires in %.0f seconds (within %d-second window)",
            seconds_until_expiry,
            _REFRESH_WINDOW_SECONDS,
        )
        needs_refresh = True
    elif saved_at_str:
        # No expires_at — use saved_at as fallback
        saved_at = datetime.fromisoformat(saved_at_str)
        if saved_at.tzinfo is None:
            saved_at = saved_at.replace(tzinfo=UTC)
        age = (now - saved_at).total_seconds()
        if age < _FALLBACK_REFRESH_SECONDS:
            return
        logger.info("No expires_at, last saved %.0f seconds ago — refreshing", age)
        needs_refresh = True
    else:
        logger.warning("Auth file has no expires_at or saved_at — skipping")
        return

    if not needs_refresh:
        return

    if not encryption_key:
        logger.error("OAUTH_ENCRYPTION_KEY not set — cannot refresh")
        return

    # Set expiring_soon before attempting refresh
    _update_auth_status(auth_file_path, SourceAuthStatus.EXPIRING_SOON)

    # Attempt refresh via T3KTokenManager
    from source_t3k.adapters.inbound.token_manager import T3KTokenManager
    from source_t3k.adapters.inbound.exceptions import T3KAPIError

    token_manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    try:
        await token_manager.get_access_token()
        _update_auth_status(auth_file_path, SourceAuthStatus.VALID)
        logger.info("T3K token refreshed successfully")
    except T3KAPIError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "re-authenticate" in error_msg.lower():
            _update_auth_status(auth_file_path, SourceAuthStatus.LOGIN_REQUIRED)
            _last_login_required_mtime = path.stat().st_mtime
            logger.error("T3K refresh token expired — run `just t3k-login`")
        else:
            _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
            logger.warning("T3K token refresh failed: %s", error_msg)
    except Exception:
        _update_auth_status(auth_file_path, SourceAuthStatus.REFRESH_FAILED)
        logger.exception("Unexpected error during T3K token refresh")
    finally:
        await token_manager.close()


class _Schedule:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds


refresh_t3k_token.labels = {"schedule": [_Schedule(300)]}  # type: ignore[attr-defined]
```

**Step 4: Import in scheduler main**

In `apps/scheduler/src/scheduler/main.py`, add:
```python
from scheduler.schedules import auth as _auth_schedules  # noqa: F401
```

**Step 5: Run test to verify it passes**

Run: `just tdd tests/unit/scheduler/test_auth_refresh_job.py`
Expected: PASS

**Step 6: Commit**

```
git add apps/scheduler/src/scheduler/schedules/auth.py apps/scheduler/src/scheduler/main.py tests/unit/scheduler/test_auth_refresh_job.py
git commit -m "feat(scheduler): add T3K token refresh job with auth gate"
```

---

### Task 7: Auth gate in source sync job

**Files:**
- Modify: `apps/worker/src/worker/jobs/source_sync.py`
- Modify: `apps/scheduler/src/scheduler/schedules/jobs.py` (`ensure_source_sync_running`)
- Test: `tests/unit/worker/test_source_sync_auth_gate.py`

**Step 1: Write the test**

```python
"""Tests for auth gate in source sync job."""

import json
from pathlib import Path
from unittest import mock

import pytest

from core.domain.value_objects.source_auth_status import SourceAuthStatus


class TestSourceSyncAuthGate:
    def test_build_api_client_checks_auth_gate(self, tmp_path: Path) -> None:
        """_build_api_client raises when auth status is not healthy."""
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
```

Note: The project bans `unittest.mock`. The test above uses `pytest.raises` and real file I/O — no mocking.

**Step 2: Run test to verify it fails**

Run: `just tdd tests/unit/worker/test_source_sync_auth_gate.py`
Expected: FAIL — _check_auth_gate not found

**Step 3: Add auth gate to source_sync.py**

Add to `apps/worker/src/worker/jobs/source_sync.py`:

```python
from core.domain.auth_gate import check_auth_status

def _check_auth_gate(auth_file_path: str | None = None) -> None:
    """Check auth status before making any T3K API calls."""
    if auth_file_path is None:
        auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    status = check_auth_status(auth_file_path)
    if not status.can_proceed():
        msg = f"T3K auth status is {status.value}"
        if status.needs_login():
            msg += " — run `just t3k-login`"
        raise RuntimeError(msg)
```

Call `_check_auth_gate()` at the start of `handle_source_sync`, before `_build_api_client()`:
```python
@broker.task
async def handle_source_sync(job_id: UUID) -> None:
    _check_auth_gate()  # Fail fast — no API calls if auth unhealthy
    ...
```

Add same gate to `ensure_source_sync_running` in `apps/scheduler/src/scheduler/schedules/jobs.py`:
```python
from core.domain.auth_gate import check_auth_status

# At start of ensure_source_sync_running:
status = check_auth_status(os.getenv("GTS_AUTH_FILE", "/.gts-auth.json"))
if not status.can_proceed():
    logger.debug("Skipping sync dispatch: auth status is %s", status.value)
    return
```

**Step 4: Run test to verify it passes**

Run: `just tdd tests/unit/worker/test_source_sync_auth_gate.py`
Expected: PASS

**Step 5: Commit**

```
git add apps/worker/src/worker/jobs/source_sync.py apps/scheduler/src/scheduler/schedules/jobs.py tests/unit/worker/test_source_sync_auth_gate.py
git commit -m "feat(worker): add auth gate to source sync job"
```

---

### Task 8: Update admin auth status endpoint

**Files:**
- Modify: `apps/worker/src/worker/schemas.py` (`AuthStatusResponse`)
- Modify: `apps/worker/src/worker/admin.py` (`get_auth_status` endpoint)
- Modify: `scripts/gts_admin.py` (`source_status` display)
- Modify: `tests/unit/worker/test_admin_api_extensions.py` (`TestSourceAuthStatus`)

**Step 1: Update AuthStatusResponse schema**

In `apps/worker/src/worker/schemas.py`, replace:
```python
class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""
    valid: bool
    method: str = "api_key"
```

With:
```python
class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""
    status: str  # SourceAuthStatus value
    can_proceed: bool
    expires_at: str | None = None
    message: str | None = None
```

**Step 2: Update get_auth_status endpoint**

In `apps/worker/src/worker/admin.py`, replace the `get_auth_status` function:

```python
@app.get("/api/admin/sources/{source}/auth/status", response_model=AuthStatusResponse)
async def get_auth_status(source: str) -> AuthStatusResponse:
    """Get auth status for a source by reading the auth file."""
    validate_source(source)

    import json
    from core.domain.auth_gate import check_auth_status

    auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    status = check_auth_status(auth_file_path)

    expires_at = None
    try:
        with open(auth_file_path) as f:
            data = json.load(f)
        expires_at = data.get("expires_at")
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        pass

    message = None
    if status.needs_login():
        message = "Run `just t3k-login` to re-authenticate"

    return AuthStatusResponse(
        status=status.value,
        can_proceed=status.can_proceed(),
        expires_at=expires_at,
        message=message,
    )
```

Add `import os` at top if not already there.

**Step 3: Update gts_admin.py source_status display**

In `scripts/gts_admin.py`, in the `source_status` function after the main status display, add an auth status call:

```python
# Also fetch auth status
auth_url = f"{base_url}/api/admin/sources/{source}/auth/status"
auth_response = await client.get(auth_url)
if auth_response.status_code == 200:
    auth_data = auth_response.json()
    auth_display = auth_data.get("status", "unknown")
    auth_msg = auth_data.get("message", "")
    if auth_msg:
        auth_display += f" — {auth_msg}"
    print(f"Auth:       {auth_display}")
```

**Step 4: Update tests**

In `tests/unit/worker/test_admin_api_extensions.py`, update `TestSourceAuthStatus`:

```python
class TestSourceAuthStatus:
    async def test_returns_auth_status(self, client: AsyncClient) -> None:
        response = await client.get("/api/admin/sources/t3k/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "can_proceed" in data
        assert isinstance(data["can_proceed"], bool)

    async def test_includes_expires_at_field(self, client: AsyncClient) -> None:
        response = await client.get("/api/admin/sources/t3k/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "expires_at" in data

    async def test_returns_404_for_unknown_source(self, client: AsyncClient) -> None:
        response = await client.get("/api/admin/sources/unknown/auth/status")
        assert response.status_code == 404
```

**Step 5: Run tests**

Run: `just tdd tests/unit/worker/test_admin_api_extensions.py::TestSourceAuthStatus`
Expected: PASS

**Step 6: Commit**

```
git add apps/worker/src/worker/schemas.py apps/worker/src/worker/admin.py scripts/gts_admin.py tests/unit/worker/test_admin_api_extensions.py
git commit -m "feat(admin): update auth status endpoint to read from auth file"
```

---

### Task 9: Just commands + login script

**Files:**
- Create: `scripts/t3k_login.py`
- Modify: `justfile`

**Step 1: Add just commands**

Add to `justfile` under `# Development Utilities`:

```just
# T3K login — authenticate via headless Chromium (runs on host)
t3k-login:
    #!/usr/bin/env bash
    set -euo pipefail
    source .env 2>/dev/null || true
    python3 scripts/t3k_login.py

# T3K auth status — check token health (runs on host, no API calls)
t3k-auth-status:
    #!/usr/bin/env bash
    set -euo pipefail
    AUTH_FILE="${GTS_AUTH_FILE:-$(dirname "$(pwd)")/.gts-auth.json}"
    if [ ! -f "$AUTH_FILE" ]; then
        echo "Auth file not found: $AUTH_FILE"
        echo "Run: just t3k-login"
        exit 1
    fi
    python3 -c "
import json, sys
data = json.load(open('$AUTH_FILE'))
status = data.get('auth_status', 'unknown')
expires = data.get('expires_at', 'not set')
user = data.get('username', 'unknown')
print(f'User:       {user}')
print(f'Status:     {status}')
print(f'Expires:    {expires}')
if status == 'login_required':
    print()
    print('Run: just t3k-login')
"
```

**Step 2: Create login script**

Create `scripts/t3k_login.py`. This uses Playwright (installed on host) to drive headless Chromium through the T3K magic-link login flow.

```python
#!/usr/bin/env python3
"""T3K Login — headless Chromium magic-link authentication.

Usage: just t3k-login

Launches headless Chromium, navigates to T3K login page, fills email,
prompts for 6-digit code, completes auth, saves encrypted tokens to
.gts-auth.json.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Auth file at worktree root (parent of any worktree dir)
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
AUTH_FILE = WORKTREE_ROOT / ".gts-auth.json"
LOGIN_EMAIL = "brewsterbear@gmail.com"
T3K_BASE_URL = "https://www.tone3000.com"


def get_encryption_key() -> str:
    """Load OAUTH_ENCRYPTION_KEY from .env file."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("OAUTH_ENCRYPTION_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if not key:
        print("Error: OAUTH_ENCRYPTION_KEY not found in .env or environment")
        sys.exit(1)
    return key


def main() -> None:
    """Run the T3K login flow."""
    try:
        from cryptography.fernet import Fernet
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install cryptography playwright")
        sys.exit(1)

    encryption_key = get_encryption_key()
    fernet = Fernet(encryption_key.encode())

    print(f"T3K Login — {LOGIN_EMAIL}")
    print(f"Auth file: {AUTH_FILE}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page()

        # Navigate to T3K login
        print("Opening T3K login page...")
        page.goto(f"{T3K_BASE_URL}/login", wait_until="networkidle")

        # Fill email
        print(f"Filling email: {LOGIN_EMAIL}")
        email_input = page.locator('input[type="email"]')
        email_input.fill(LOGIN_EMAIL)

        # Submit email
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()
        page.wait_for_load_state("networkidle")

        # Prompt for verification code
        print()
        code = input("Enter 6-digit code from email: ").strip()
        if len(code) != 6 or not code.isdigit():
            print("Error: Expected 6-digit numeric code")
            browser.close()
            sys.exit(1)

        # Fill code
        code_input = page.locator('input[name="code"], input[type="text"]')
        code_input.fill(code)

        # Submit code
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()

        # Wait for redirect / auth completion
        print("Waiting for authentication...")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Extract tokens from cookies/storage
        cookies = page.context.cookies()
        access_token = None
        refresh_token = None

        for cookie in cookies:
            if "access" in cookie["name"].lower() or "token" in cookie["name"].lower():
                if not access_token:
                    access_token = cookie["value"]
            if "refresh" in cookie["name"].lower():
                refresh_token = cookie["value"]

        # Also check localStorage
        if not access_token:
            access_token = page.evaluate(
                "() => localStorage.getItem('access_token') || sessionStorage.getItem('access_token')"
            )
        if not refresh_token:
            refresh_token = page.evaluate(
                "() => localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token')"
            )

        browser.close()

        if not access_token:
            print("Error: Could not extract access token from browser session")
            print("The login flow may have changed. Check T3K manually.")
            sys.exit(1)

        # Encrypt and save
        auth_data = {}
        if AUTH_FILE.exists():
            try:
                auth_data = json.loads(AUTH_FILE.read_text())
            except json.JSONDecodeError:
                pass

        auth_data["access_token"] = fernet.encrypt(access_token.encode()).decode()
        if refresh_token:
            auth_data["refresh_token"] = fernet.encrypt(refresh_token.encode()).decode()
        auth_data["expires_at"] = None  # Unknown — refresh job will determine
        auth_data["auth_status"] = "valid"
        auth_data["saved_at"] = datetime.now(UTC).isoformat()

        AUTH_FILE.write_text(json.dumps(auth_data, indent=2))
        os.chmod(AUTH_FILE, 0o600)

        print()
        print(f"Login successful. Auth saved to {AUTH_FILE}")


if __name__ == "__main__":
    main()
```

Note: This script is a starting point. The exact T3K login page selectors and token extraction will likely need adjustment based on the actual T3K UI. The implementer should test interactively and adjust selectors as needed.

**Step 3: Commit**

```
git add scripts/t3k_login.py justfile
git commit -m "feat: add T3K login script and just commands"
```

---

### Task 10: Update gts-auth skill doc

**Files:**
- Modify: `.claude/skills/gts-auth/SKILL.md`
- Modify: `.claude/skills/gts-auth/references/auth-file.md` (if it exists)

**Step 1: Update SKILL.md**

Add a row to the table:
```
| T3K login, token refresh, SourceAuthStatus | references/login-refresh.md |
```

**Step 2: Create references/login-refresh.md**

Document:
- `just t3k-login` — headless Chromium login flow
- `just t3k-auth-status` — check auth health from host
- `SourceAuthStatus` enum values and what each means
- Auth gate: `check_auth_status()` — called before any T3K API work
- Scheduled refresh: runs every 5 min in scheduler
- Recovery: `LOGIN_REQUIRED` → run `just t3k-login`
- Rate limit caution: no retries, single attempt per 5-min tick

**Step 3: Commit**

```
git add .claude/skills/gts-auth/
git commit -m "docs: update gts-auth skill with login and refresh flow"
```

---

## Task dependency order

```
Task 1 (enum) → Task 2 (gate) → Task 3 (token manager writes status)
                                → Task 7 (gate in sync job)
                                → Task 8 (admin endpoint)
Task 4 (infra) → Task 5 (fix crash) → Task 6 (refresh job)
Task 9 (login script) — independent
Task 10 (docs) — last
```

Tasks 1→2→3 and 4→5→6 can run in parallel as two independent tracks.
Task 7 depends on Task 2. Task 8 depends on Task 2.
Task 9 is independent of everything.
Task 10 is last.
