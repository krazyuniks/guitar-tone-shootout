# T3KTokenManager Auth File Rewrite — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite T3KTokenManager to load encrypted OAuth tokens from .gts-auth.json and refresh via POST /api/v1/auth/session/refresh, replacing the broken API key exchange that Vercel blocks.

**Architecture:** T3KTokenManager becomes a self-contained token lifecycle manager. It reads Fernet-encrypted tokens from .gts-auth.json, decrypts them, caches in memory, and refreshes via the T3K refresh endpoint when expired. Fernet encrypt/decrypt logic is inlined (duplicated from webapp) because source_t3k cannot import from webapp per dependency rules.

**Tech Stack:** Python, httpx, cryptography (Fernet), asyncio

---

## Important context

- **Env var for encryption:** The actual configured env var is `OAUTH_ENCRYPTION_KEY` (in docker-compose.yml and .env.example). The webapp's `TokenEncryptor` reads `GTS_ENCRYPTION_KEY` but these may or may not be mapped. To avoid confusion, the token_manager accepts the encryption key as a constructor parameter — the caller reads whatever env var they want.
- **Auth file location:** In Docker the auth file is at `/worktrees/.gts-auth.json` (webapp already mounts `..:/worktrees`). The worker needs the same mount added.
- **Worker doesn't auto-reload** — after code changes, run `docker compose restart worker`.
- **No mocking** — tests use httpx MockTransport, not unittest.mock.
- **Run tests with** `just tdd <path>`.
- **The api_client.py line 147** clears `self._token_manager._access_token = None` on 401 retry. The new token_manager still has `_access_token` so this continues to work.

---

### Task 1: Add cryptography dependency to source_t3k

**Files:**
- Modify: `sources/t3k/pyproject.toml`

**Step 1: Add dependency**

Add `"cryptography>=44.0.0"` to the dependencies list in `sources/t3k/pyproject.toml`:

```toml
dependencies = [
    "gts-core",
    "httpx>=0.28.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "pgmq-sqlalchemy>=0.1.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "cryptography>=44.0.0",
]
```

**Step 2: Commit**

```bash
git add sources/t3k/pyproject.toml
git commit -m "build(t3k): add cryptography dependency for auth file decryption"
```

---

### Task 2: Rewrite T3KTokenManager

**Files:**
- Modify: `sources/t3k/src/source_t3k/adapters/inbound/token_manager.py`

**Step 1: Write the new token_manager.py**

Replace the entire file with:

```python
"""T3K API token manager.

Loads encrypted OAuth tokens from .gts-auth.json, decrypts them with
Fernet, caches in memory, and refreshes via POST /api/v1/auth/session/refresh
when near expiry.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from httpx import AsyncClient

from source_t3k.adapters.inbound.exceptions import T3KAPIError
from source_t3k.adapters.inbound.vercel_solver import is_vercel_challenge, solve_challenge

logger = logging.getLogger(__name__)

# Refresh token when within this many seconds of expiry.
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


class T3KTokenManager:
    """Manages OAuth token lifecycle for T3K API authentication.

    Loads encrypted tokens from .gts-auth.json, decrypts with Fernet,
    and refreshes via the T3K refresh endpoint when expired.
    """

    def __init__(self, auth_file_path: str, base_url: str, encryption_key: str) -> None:
        self._auth_file_path = auth_file_path
        self._base_url = base_url.rstrip("/")
        self._fernet = Fernet(encryption_key.encode("utf-8") if isinstance(encryption_key, str) else encryption_key)
        self._client = AsyncClient(
            headers={
                "User-Agent": "GuitarToneShootout/1.0 (sync; +https://github.com/krazyuniks/guitar-tone-shootout)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self._lock = asyncio.Lock()

        # Cached token state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0  # unix timestamp

    async def get_access_token(self) -> str:
        """Return a valid access token, loading or refreshing as needed."""
        if self._access_token and time.time() < self._expires_at - _REFRESH_BUFFER_SECONDS:
            return self._access_token

        async with self._lock:
            # Double-check after acquiring lock
            if self._access_token and time.time() < self._expires_at - _REFRESH_BUFFER_SECONDS:
                return self._access_token

            if self._access_token is None:
                self._load_from_auth_file()

            if time.time() >= self._expires_at - _REFRESH_BUFFER_SECONDS:
                await self._refresh()

            assert self._access_token is not None
            return self._access_token

    def _load_from_auth_file(self) -> None:
        """Load and decrypt tokens from .gts-auth.json."""
        path = Path(self._auth_file_path)
        if not path.exists():
            raise T3KAPIError(f"Auth file not found at {self._auth_file_path} — authenticate via browser")

        with open(path) as f:
            data = json.load(f)

        encrypted_access = data.get("access_token")
        if not encrypted_access:
            raise T3KAPIError("No access_token in auth file — authenticate via browser")

        try:
            self._access_token = self._fernet.decrypt(encrypted_access.encode("utf-8")).decode("utf-8")
        except InvalidToken as e:
            raise T3KAPIError("Token decryption failed — re-authenticate via browser") from e

        encrypted_refresh = data.get("refresh_token")
        if encrypted_refresh:
            try:
                self._refresh_token = self._fernet.decrypt(encrypted_refresh.encode("utf-8")).decode("utf-8")
            except InvalidToken as e:
                raise T3KAPIError("Refresh token decryption failed — re-authenticate via browser") from e

        expires_at_str = data.get("expires_at")
        if expires_at_str:
            expires_dt = datetime.fromisoformat(expires_at_str)
            self._expires_at = expires_dt.timestamp()
        else:
            # No expiry info — assume valid for 1 hour from now
            self._expires_at = time.time() + 3600

        logger.info("Loaded T3K tokens from auth file")

    async def _refresh(self) -> None:
        """Refresh the access token via POST /api/v1/auth/session/refresh."""
        if not self._refresh_token:
            raise T3KAPIError("No refresh token — re-authenticate via browser")

        for attempt in range(3):
            response = await self._client.post(
                f"{self._base_url}/api/v1/auth/session/refresh",
                json={
                    "refresh_token": self._refresh_token,
                    "access_token": self._access_token or "",
                },
            )

            if response.status_code == 401:
                raise T3KAPIError("T3K refresh token expired — re-authenticate via browser")

            if is_vercel_challenge(response.status_code, response.text):
                logger.warning("Vercel challenge on refresh (attempt %d/3)", attempt + 1)
                if solve_challenge(self._base_url):
                    continue
                raise T3KAPIError("Vercel challenge could not be solved during token refresh")

            response.raise_for_status()

            data = response.json()
            new_access = data["access_token"]
            new_refresh = data.get("refresh_token", self._refresh_token)
            expires_in = data.get("expires_in", 3600)

            # Update in-memory cache
            self._access_token = new_access
            self._refresh_token = new_refresh
            self._expires_at = time.time() + expires_in

            # Encrypt and save to auth file
            self._save_to_auth_file(new_access, new_refresh, expires_in)

            logger.info("T3K token refreshed, expires in %ds", expires_in)
            return

        raise T3KAPIError("Token refresh failed after Vercel challenge retries")

    def _save_to_auth_file(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """Encrypt tokens and update .gts-auth.json."""
        path = Path(self._auth_file_path)

        # Load existing data to preserve user_id, username, etc.
        existing: dict = {}
        if path.exists():
            with open(path) as f:
                existing = json.load(f)

        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        expires_at_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

        existing["access_token"] = self._fernet.encrypt(access_token.encode("utf-8")).decode("utf-8")
        existing["refresh_token"] = self._fernet.encrypt(refresh_token.encode("utf-8")).decode("utf-8")
        existing["expires_at"] = expires_at_iso
        existing["saved_at"] = datetime.now(timezone.utc).isoformat()

        with open(path, "w") as f:
            json.dump(existing, f, indent=2)

        os.chmod(path, 0o600)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
```

**Step 2: Run existing tests to check for import/syntax errors**

```bash
just tdd tests/unit/t3k/test_api_client.py
```

Expected: FAIL — `_make_token_manager()` still uses old constructor signature `(api_key=..., base_url=...)`.

**Step 3: Commit**

```bash
git add sources/t3k/src/source_t3k/adapters/inbound/token_manager.py
git commit -m "feat(t3k): rewrite T3KTokenManager to use auth file + refresh flow"
```

---

### Task 3: Update test helper for new constructor

**Files:**
- Modify: `tests/unit/t3k/test_api_client.py`

**Step 1: Update `_make_token_manager` and `_auth_handler`**

Replace lines 20-33 with:

```python
def _make_token_manager() -> T3KTokenManager:
    """Create a token manager with a pre-set token (bypasses auth file loading)."""
    tm = T3KTokenManager(
        auth_file_path="/tmp/fake-auth.json",
        base_url="https://t3k.test",
        encryption_key=Fernet.generate_key().decode(),
    )
    # Pre-fill token so it never tries to load from auth file
    tm._access_token = "fake-jwt"
    tm._expires_at = 9999999999.0
    return tm
```

Also add import at top of file:

```python
from cryptography.fernet import Fernet
```

Remove the unused `_auth_handler` function (lines 20-22 in original).

**Step 2: Run tests**

```bash
just tdd tests/unit/t3k/test_api_client.py
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add tests/unit/t3k/test_api_client.py
git commit -m "test(t3k): update test helper for new T3KTokenManager constructor"
```

---

### Task 4: Update _build_api_client in source_sync.py

**Files:**
- Modify: `apps/worker/src/worker/jobs/source_sync.py`

**Step 1: Update `_build_api_client` function**

Replace lines 30-36 with:

```python
def _build_api_client() -> tuple[T3KTokenManager, T3KAPIClient]:
    """Build T3K token manager + API client from environment configuration."""
    base_url = os.getenv("T3K_API_URL", "https://www.tone3000.com")
    auth_file_path = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
    encryption_key = os.environ["OAUTH_ENCRYPTION_KEY"]
    token_manager = T3KTokenManager(
        auth_file_path=auth_file_path,
        base_url=base_url,
        encryption_key=encryption_key,
    )
    api_client = T3KAPIClient(token_manager=token_manager, base_url=base_url)
    return token_manager, api_client
```

Note: `OAUTH_ENCRYPTION_KEY` is required (uses `os.environ[]` not `os.getenv()`). If missing, the worker will fail fast with a clear KeyError rather than silently proceeding.

**Step 2: Commit**

```bash
git add apps/worker/src/worker/jobs/source_sync.py
git commit -m "feat(worker): use auth file for T3K token manager instead of API key"
```

---

### Task 5: Add auth file mount and env vars for worker container

**Files:**
- Modify: `worktree/templates/docker-compose.override.yml.j2`
- Modify: `worktree/templates.py`
- Modify: `docker-compose.yml` (add OAUTH_ENCRYPTION_KEY to worker environment)

**Step 1: Add OAUTH_ENCRYPTION_KEY and GTS_AUTH_FILE to worker in docker-compose.yml**

In the worker service environment section (after line 153 in `docker-compose.yml`), add:

```yaml
      OAUTH_ENCRYPTION_KEY: ${OAUTH_ENCRYPTION_KEY:-dev_oauth_key_32_bytes_exactly!!}
```

**Step 2: Add auth file mount to worker in worktree template (Jinja2)**

In `worktree/templates/docker-compose.override.yml.j2`, find the worker section and add the parent dir mount and env var. The worker section should become:

```yaml
  worker:
    container_name: {{ worktree.compose_project }}-worker
    volumes:
      ...existing volumes...
      # Parent dir for shared auth file (.gts-auth.json)
      - ../:/worktrees
    environment:
      - GTS_AUTH_FILE=/worktrees/.gts-auth.json
```

**Step 3: Add same to templates.py**

In `worktree/templates.py`, find the worker section in the template string and add the same volume mount and env var.

**Step 4: Regenerate the main worktree override**

```bash
./worktree.py setup main
```

**Step 5: Commit**

```bash
git add docker-compose.yml worktree/templates/docker-compose.override.yml.j2 worktree/templates.py
git commit -m "infra(worker): add auth file mount and encryption key for T3K token manager"
```

---

### Task 6: Integration test — run source sync

**Step 1: Restart worker to pick up code changes**

```bash
docker compose restart worker
```

**Step 2: Trigger a source sync**

```bash
just admin source-sync t3k
```

**Step 3: Check worker logs**

```bash
docker compose logs worker --tail 50 --since 60s
```

Expected: Should see "Loaded T3K tokens from auth file" log message, followed by sync activity (not a 403 Vercel challenge).

**Step 4: Verify queue has messages**

```bash
docker compose exec -T db psql -U gts -d gts_t3k_source -c "SELECT count(*) FROM pgmq.q_gear_sync;"
```

**Step 5: Verify gear rows**

```bash
docker compose exec -T db psql -U gts -d gts_core -c "SELECT count(*) FROM gear;"
```

---

### Task 7: Update .env.example

**Files:**
- Modify: `.env.example`

**Step 1: Remove T3K_API_KEY, update comments**

Replace lines 96-104 with:

```
# =============================================================================
# T3K Source Adapter
# =============================================================================

# T3K API base URL (default: https://www.tone3000.com)
# T3K_API_URL=https://www.tone3000.com

# Auth file path (default: /.gts-auth.json in Docker)
# GTS_AUTH_FILE=/.gts-auth.json
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: update .env.example — remove T3K_API_KEY, add auth file config"
```
