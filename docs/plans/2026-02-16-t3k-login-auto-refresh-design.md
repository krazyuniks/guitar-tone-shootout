# T3K Official Login & Auto-Refresh Design

## Context

T3K authentication moved from API key exchange to encrypted OAuth tokens stored
in `.gts-auth.json`. The token manager loads/decrypts/refreshes these tokens.
What's missing: an official login flow and proactive scheduled refresh.

## Section 1: Login CLI

**Script**: `scripts/t3k_login.py` + `just t3k-login` (runs on host, not Docker).

Flow:
1. Launch headless Chromium via CDP (`/usr/bin/chromium`)
2. Navigate to T3K magic-link login page
3. Fill email (`brewsterbear@gmail.com`)
4. Prompt user for 6-digit code from email
5. Submit code, wait for auth callback
6. Extract tokens from browser session
7. Encrypt with Fernet (`OAUTH_ENCRYPTION_KEY` from `.env`)
8. Write to `.gts-auth.json` with `auth_status: valid`
9. `chmod 600`

Single attempt. No retries. If it fails, user re-runs.

## Section 2: Scheduled Token Refresh + Auth Gate

### Core principle

No T3K API call unless auth is verified healthy. Every path that touches the
T3K API checks `SourceAuthStatus` from the auth file before making network
calls. If status isn't `VALID` or `EXPIRING_SOON`, fail fast. Zero wasted
API calls.

### SourceAuthStatus enum

New value object in `core/domain/value_objects/source_auth_status.py`:

```python
class SourceAuthStatus(str, Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    REFRESH_FAILED = "refresh_failed"    # transient — next tick retries
    LOGIN_REQUIRED = "login_required"    # terminal — manual login needed
    UNKNOWN = "unknown"                  # auth file missing or unreadable
```

Stored as plaintext in `.gts-auth.json`: `"auth_status": "valid"`.
Readable without decryption.

### Auth gate function

```python
def check_auth_status(auth_file_path: str) -> SourceAuthStatus:
    """Read auth_status from auth file. No decryption, no API calls."""
```

Callers use as preflight:
- `VALID` / `EXPIRING_SOON` → proceed
- `REFRESH_FAILED` → fail fast, log "token refresh pending, skipping"
- `LOGIN_REQUIRED` → fail fast, log "run `just t3k-login`"
- `UNKNOWN` → fail fast, log "auth file missing or corrupt"

Gate enforced at:
- `ensure_source_sync_running()` — before TaskIQ dispatch
- `SyncService.run()` — before first API call
- Future T3K consumers — same pattern

### Scheduled refresh job

New file: `apps/scheduler/src/scheduler/schedules/auth.py`. Runs every 5 min.

1. Read auth file (plaintext fields: `expires_at`, `auth_status`, `saved_at`)
2. If `auth_status` is `LOGIN_REQUIRED` → skip, log debug
3. If token expires in >10 min → ensure status is `VALID`, skip
4. If token expires in ≤10 min → set `EXPIRING_SOON`, instantiate
   `T3KTokenManager`, call `get_access_token()` (triggers refresh)
5. If no `expires_at` → refresh if >30 min since `saved_at`
6. On success → set `VALID`, log info
7. On 401 → set `LOGIN_REQUIRED`, log error with recovery message.
   No further attempts until auth file mtime changes (`just t3k-login` ran)
8. On other error → set `REFRESH_FAILED`, log warning.
   Next 5-min tick retries naturally. No retry loop inside the job.

### Admin visibility

`just admin source-status t3k` includes auth status:

```
Sync Status: t3k
──────────────────────────────────────────────────
Status:     idle
Enabled:    True
Auth:       LOGIN_REQUIRED — run `just t3k-login`
──────────────────────────────────────────────────
```

Worker reads auth status from the mounted auth file.

## Section 3: CLI Commands & Skill Updates

### Just commands

| Command | Description |
|---------|-------------|
| `just t3k-login` | Run login script on host (headless Chromium) |
| `just t3k-auth-status` | Read auth file, print status + expiry (host, no API calls) |

Both run on host — auth file lives outside containers.

### Skill doc update

Update `.claude/skills/gts-auth/SKILL.md`:
- Login flow (`just t3k-login`)
- Auth file location and format
- `SourceAuthStatus` enum values and meanings
- Recovery: `LOGIN_REQUIRED` → `just t3k-login`

### Scheduler crash-loop prerequisite

`jobs.py` imports from `webapp.adapters` (violates dependency rules, causes
`ModuleNotFoundError`). Must be fixed before the refresh job can run.
Separate implementation task.

## Technical details

- Chromium: `/usr/bin/chromium` (Debian package)
- Login email: `brewsterbear@gmail.com`
- Auth file: `/home/ryan/Work/guitar-tone-worktrees/.gts-auth.json`
- Encryption: `OAUTH_ENCRYPTION_KEY` in `.env` (Fernet)
- Docker mapping: `OAUTH_ENCRYPTION_KEY` → `GTS_ENCRYPTION_KEY`
- Refresh endpoint: `POST /api/v1/auth/session/refresh`
- Rate limit caution: single attempts only, no aggressive retries anywhere
