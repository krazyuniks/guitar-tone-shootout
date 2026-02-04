# Authentication Rules

## T3K Authentication Model

**T3K uses passwordless OAuth.** Users authenticate via email magic link on T3K's site - no passwords exist.

GTS integrates via OAuth2:
1. User clicks "Login with T3K" → redirected to T3K
2. T3K sends email link to user → user clicks link
3. T3K redirects back with OAuth code → GTS exchanges for tokens
4. Tokens stored in `.gts-auth.json` for worktree sharing

**No user credentials are stored or managed by GTS.** Only OAuth access/refresh tokens.

---

## API Authentication Architecture

GTS separates user-facing APIs from internal admin operations. Admin APIs are decentralised — each component owns its own admin endpoints.

### User API (Webapp — port 8000)

| Route Prefix | Purpose | Auth Required |
|--------------|---------|---------------|
| `/api/v1/jobs` | User's own jobs | `CurrentUser` |
| `/api/v1/auth` | Auth operations | Varies by endpoint |
| `/api/v1/*` | All user operations | `CurrentUser` |

User endpoints require `CurrentUser` authentication via session cookie.
Users can only access their own resources.

### Internal Admin API (Worker — port 8001)

Admin endpoints have NO authentication. Access is controlled at the network level — port not exposed publicly.

All admin endpoints served by the worker container:

```
/admin/jobs/              # Job list with status filter
/admin/jobs/{id}          # Job details
/admin/jobs/dead-lettered # Dead-lettered jobs
/admin/jobs/{id}/retry    # Retry failed job
/admin/t3k/sync/status    # Current sync state
/admin/t3k/sync           # Trigger catalog sync (POST)
/admin/t3k/sync/stats     # Pack/model counts
/admin/t3k/auth/status    # T3K OAuth token validity
/health                   # Composite health check
```

**Why worker serves T3K endpoints:** Worker already connects to `gts_t3k_source` for the pgmq consumer, so it can query sync status from the same database.

**CLI Tool:**
```bash
# All commands → Worker (port 8001)
gts-admin jobs            # List all jobs
gts-admin job <id>        # Get job details
gts-admin t3k-status      # Sync status
gts-admin auth-status     # T3K auth check
```

**Reference:** [GTS-Technical-Architecture Wiki](https://github.com/krazyuniks/guitar-tone-shootout/wiki/GTS-Technical-Architecture#admin-api-architecture)

---

## Auth Persistence System

T3K authentication is centralized across all worktrees using a shared auth file.

### Key Concept

**Login once, work everywhere.** After authenticating via OAuth in any worktree, the credentials are saved to a shared file that all worktrees can use.

### Auth File Location

```
guitar-tone-shootout-worktrees/.gts-auth.json
```

This file contains:
- T3K user ID and username
- OAuth access and refresh tokens
- Token expiration time

**Security:** File has restricted permissions (600) - only owner can read/write. See Security Considerations section below.

### Worktree.py Auth Commands

| Command | Purpose |
|---------|---------|
| `./worktree.py auth-status` | Show auth validity and expiration |
| `./worktree.py auth-login` | Open browser for T3K OAuth |
| `./worktree.py auth-restore` | Restore session in current worktree |

### Workflow

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

### Session Duration

- Session cookies: 7 days (extended from 30 min)
- T3K tokens: depends on T3K refresh token validity
- Tokens auto-saved after each OAuth flow

### Checking Auth Status

**Before T3K-dependent work:**
```bash
./worktree.py auth-status
```

**In code (backend):**
```bash
curl http://localhost:8000/api/v1/auth/status
```

### Session Start Hook

The auth-check hook runs at session start and will:
- Show current auth status
- Warn if tokens expire within 24 hours
- Inform if no auth is available

### Backend API Endpoints

| Endpoint | Auth Required | Purpose |
|----------|---------------|---------|
| `GET /auth/status` | No | Check auth file validity |
| `POST /auth/save-session` | Yes | Save current tokens to file |
| `POST /auth/restore-session` | No | Restore session from file |
| `GET /auth/me` | Optional | Get current user info |

### Troubleshooting

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

---

## Security Considerations

> **See also:** [Security Rules](.claude/rules/security.md) for comprehensive security practices including OWASP Top 10, dependency scanning, and secret management.

### Auth File Security (.gts-auth.json)

The auth file stores sensitive OAuth tokens that grant access to T3K API.

**File Permissions:**
- File is created with mode 0600 (owner read/write only)
- `worktree/auth.py` validates permissions on every read
- Insecure permissions are auto-fixed when possible

**Automatic Protection:**
- Permissions checked each time auth file is read
- Warning printed to stderr if permissions cannot be fixed
- File ownership verified to match current user

**Manual Verification:**
```bash
ls -la $(dirname $(pwd))/.gts-auth.json
# Should show: -rw------- (600)

# Fix manually if needed:
chmod 600 $(dirname $(pwd))/.gts-auth.json
```

**Alternative: OS Keychain Storage**

Trade-offs of using OS keychain (macOS Keychain, Windows Credential Manager):
- Pro: Encrypted at rest by OS
- Pro: Access control via OS permissions
- Con: Platform-specific implementation required
- Con: Cannot be shared across worktrees via simple file mount
- Con: Adds dependency on keychain libraries

Current approach uses file-based storage for cross-worktree simplicity. Keychain integration may be considered for production deployments.

### Session Cookie Security

Session cookies are configured with security attributes:

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly` | `True` | Prevents JavaScript access (XSS protection) |
| `secure` | `True` in production | Cookie only sent over HTTPS |
| `samesite` | `lax` | Prevents CSRF on cross-site POST requests |

**Production vs Development:**
- Development: `secure=False` to allow HTTP
- Production: `secure=True` enforced (HTTPS required)

### CSRF Protection

State-changing operations use the `SameSite=Lax` cookie attribute:
- GET requests: Cookie sent (allows normal navigation)
- Cross-origin POST/PUT/DELETE: Cookie NOT sent (CSRF protection)

For forms submitted via HTMX:
- HTMX requests include the session cookie automatically
- `hx-post`, `hx-put`, `hx-delete` are protected by SameSite

Additional CSRF token not currently required due to:
1. All state-changing operations require authenticated session cookie
2. SameSite=Lax prevents cross-origin form submissions
3. CORS policy restricts cross-origin API requests

### Security Headers

Security headers are configured in nginx.conf.template:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer info |
| `Content-Security-Policy` | Report-only mode | XSS/injection defense |
| `Strict-Transport-Security` | Set via HTTPS detection | Forces HTTPS |

**CSP Policy:**
- `default-src 'self'`: Only same-origin by default
- `script-src 'self' 'unsafe-inline' https://unpkg.com`: Scripts from self, inline (Alpine), HTMX CDN
- `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`: Styles with Google Fonts
- `font-src 'self' https://fonts.gstatic.com`: Fonts from Google
- `connect-src 'self' ws: wss:`: API and WebSocket connections
- `frame-ancestors 'none'`: Disallow embedding in frames

CSP is in **report-only mode** initially to identify violations without breaking functionality.
