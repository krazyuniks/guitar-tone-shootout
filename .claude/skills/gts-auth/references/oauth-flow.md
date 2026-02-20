# T3K Authentication

GTS has two separate auth paths for T3K. Do not confuse them.

## Webapp Login (OAuth)

T3K uses passwordless OAuth. Users authenticate via email magic link on T3K's site -- no passwords exist.

GTS integrates via OAuth2:

1. User clicks "Login with T3K" -- redirected to T3K
2. T3K sends email link to user -- user clicks link
3. T3K redirects back with OAuth code -- GTS exchanges for tokens
4. Tokens stored in `.gts-auth.json` for worktree sharing

**No user credentials are stored or managed by GTS.** Only OAuth access/refresh tokens.

## Source Sync (API Key → JWT)

The T3K source adapter authenticates via API key, not OAuth tokens.

1. `T3K_API_KEY` env var set in t3k-sync container
2. `T3KTokenManager` exchanges API key for JWT via `POST /api/v1/auth/session`
3. JWT cached in memory, auto-refreshed before expiry (5 min buffer)
4. No database token storage — purely in-memory lifecycle

**Key files:**
- `sources/t3k/src/source_t3k/adapters/inbound/token_manager.py` — JWT exchange and refresh
- `apps/worker/src/worker/jobs/source_sync.py` — creates token manager from env var
