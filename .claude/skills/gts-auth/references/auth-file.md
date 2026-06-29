# Auth Persistence System

## Key Concept

**Login once, work everywhere.** After authenticating via OAuth in any worktree, the credentials are saved to a shared file that all worktrees can use.

## Auth File Location

```
guitar-tone-shootout-worktrees/.gts-auth.json
```

This file contains:
- T3K user ID and username
- OAuth access and refresh tokens
- Token expiration time

## File Permissions

- File is created with mode 0600 (owner read/write only)
- `scripts/t3k_auth.py` reads the shared auth file for status and restore
- Insecure permissions are auto-fixed when possible
- Permissions checked each time auth file is read
- Warning printed to stderr if permissions cannot be fixed
- File ownership verified to match current user

**Manual verification:**
```bash
ls -la $(dirname $(pwd))/.gts-auth.json
# Should show: -rw------- (600)

# Fix manually if needed:
chmod 600 $(dirname $(pwd))/.gts-auth.json
```

## Auth Commands

| Command | Purpose |
|---------|---------|
| `just t3k-auth` | Canonical auth flow: check status, login if needed, restore session |
| `just t3k-login` | Direct headless Chromium magic-link login only |
| `just t3k-auth-status` | Show auth validity and expiration |

## Workflow

**Initial Setup (once):**
1. Start a worktree with backend running
2. Run `just t3k-auth`
3. Complete the passcode flow if prompted
4. Tokens are saved and the session is restored automatically

**New Worktree (automatic):**
1. `worktree up gts <branch>` creates + provisions the feature worktree
2. `just t3k-auth` restores the saved auth into the running webapp when valid tokens exist
3. Ready to work with T3K API

## Checking Auth Status

**Before T3K-dependent work:**
```bash
just t3k-auth-status
```

**In code (backend):**
```bash
curl http://localhost:8000/auth/status
```

## Session Start Hook

The auth-check hook runs at session start and will:
- Show current auth status
- Warn if tokens expire within 24 hours
- Inform if no auth is available

## Backend API Endpoints

| Endpoint | Auth Required | Purpose |
|----------|---------------|---------|
| `GET /auth/status` | No | Check auth file validity |
| `POST /auth/save-session` | Yes | Save current tokens to file |
| `POST /auth/restore-session` | No | Restore session from file |
| `GET /auth/me` | Optional | Get current user info |

## Troubleshooting

**"No saved auth data"**
- Run `just t3k-auth` to authenticate

**"Tokens expired"**
- Run `just t3k-auth` to re-authenticate

**"Cannot connect to backend"**
- Ensure Docker services are running
- Check backend port matches worktree's configured port

**Auth restore fails after setup**
- Backend may still be starting up
- Wait a few seconds and run `just t3k-auth`
