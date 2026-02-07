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
- `worktree/auth.py` validates permissions on every read
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

## Worktree.py Auth Commands

| Command | Purpose |
|---------|---------|
| `./worktree.py auth-status` | Show auth validity and expiration |
| `./worktree.py auth-login` | Open browser for T3K OAuth |
| `./worktree.py auth-restore` | Restore session in current worktree |

## Workflow

**Initial Setup (once):**
1. Start a worktree with backend running
2. Run `./worktree.py auth-login --port <backend-port>`
3. Complete OAuth in browser
4. Tokens saved automatically

**New Worktree (automatic):**
1. `./worktree.py setup <issue>` creates worktree
2. Auth auto-restores if valid tokens exist
3. Ready to work with T3K API

**Manual Restore (if needed):**
```bash
./worktree.py auth-restore
```

## Checking Auth Status

**Before T3K-dependent work:**
```bash
./worktree.py auth-status
```

**In code (backend):**
```bash
curl http://localhost:8000/api/v1/auth/status
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
- Run `./worktree.py auth-login` to authenticate

**"Tokens expired"**
- Run `./worktree.py auth-login` to re-authenticate

**"Cannot connect to backend"**
- Ensure Docker services are running
- Check backend port matches worktree's configured port

**Auth restore fails after setup**
- Backend may still be starting up
- Wait a few seconds and run `./worktree.py auth-restore`
