# Security Rules

## OWASP Top 10 Checklist

Before any PR, verify:

| Category | Verification |
|----------|--------------|
| **Injection** | SQLAlchemy ORM or parameterised queries. Never f-strings with SQL. |
| **Broken Authentication** | Session cookies with `httponly`, `secure`, `samesite=lax`. |
| **Sensitive Data Exposure** | No secrets in code. HTTPS in production. |
| **Broken Access Control** | Check `current_user` ownership on all resources. |
| **Security Misconfiguration** | CSP headers, CORS restricted, admin routes blocked. |
| **XSS** | Auto-escaping enabled (Astro/React/Jinja2). No raw HTML injection. |
| **Insecure Deserialization** | Pydantic validation on all inputs. |
| **Vulnerable Components** | `pip-audit` and `npm audit` clean. |
| **Logging & Monitoring** | Auth failures logged. No secrets in logs. |

---

## Critical Rules

### 1. Never Commit Secrets

- No API keys, passwords, or tokens in code
- Use environment variables via `.env`
- Check `.env.example` is sanitised (no real values)
- Use `gitleaks` to detect accidentally committed secrets

```bash
# Verify no secrets committed
gitleaks detect --source . --config .gitleaks.toml --verbose
```

### 2. SQL Injection Prevention

Always use SQLAlchemy ORM or parameterised queries. Never interpolate user input.

```python
# WRONG - vulnerable to SQL injection
db.execute(f"SELECT * FROM users WHERE id = {user_id}")
db.execute(text(f"SELECT * FROM users WHERE name = '{name}'"))

# RIGHT - parameterised
db.execute(select(User).where(User.id == user_id))
db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

### 3. XSS Prevention

Template engines auto-escape by default. Never bypass this protection.

| Engine | Auto-escapes | Dangerous (NEVER use) |
|--------|--------------|----------------------|
| Astro | Yes | `set:html` |
| React | Yes | `dangerouslySetInnerHTML` |
| Jinja2 | Yes | `| safe` filter |

### 4. Auth Checks

All protected routes must verify authentication and authorisation.

```python
# Verify user owns the resource (prevents IDOR)
if shootout.user_id != current_user.id:
    raise HTTPException(status_code=404)  # 404 not 403 (don't leak existence)
```

### 5. CORS Configuration

```python
# WRONG - allows any origin
allow_origins=["*"]

# RIGHT - restrict to known origins
allow_origins=["https://yourdomain.com"]
```

---

## Security Headers

Security headers are configured in `nginx.conf.template`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer info |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS protection |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS (production) |

### Content Security Policy (CSP)

CSP prevents XSS and injection attacks by restricting resource origins. Currently in **report-only mode** to identify violations without breaking functionality.

```
default-src 'self';
script-src 'self' 'unsafe-inline' https://unpkg.com;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' ws: wss:;
frame-ancestors 'none';
```

| Directive | Value | Rationale |
|-----------|-------|-----------|
| `default-src` | `'self'` | Only same-origin by default |
| `script-src` | `'self' 'unsafe-inline' https://unpkg.com` | Alpine.js requires inline, HTMX from CDN |
| `style-src` | `'self' 'unsafe-inline' https://fonts.googleapis.com` | Tailwind inline styles, Google Fonts |
| `font-src` | `'self' https://fonts.gstatic.com` | Google Fonts assets |
| `img-src` | `'self' data: https:` | Data URIs for inline images, external images |
| `connect-src` | `'self' ws: wss:` | API and WebSocket connections |
| `frame-ancestors` | `'none'` | Prevent embedding in iframes |

**Verify headers:**
```bash
curl -I http://localhost:9000 | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport)"
```

---

## CSRF Protection

Cross-Site Request Forgery is prevented through cookie configuration:

| Cookie Attribute | Value | Protection |
|-----------------|-------|------------|
| `httponly` | `True` | Prevents JavaScript access (XSS protection) |
| `secure` | `True` (prod) | Cookie only sent over HTTPS |
| `samesite` | `lax` | Blocks cross-origin POST/PUT/DELETE |

**How SameSite=Lax works:**
- GET requests: Cookie sent (allows normal navigation)
- Cross-origin POST/PUT/DELETE: Cookie NOT sent (CSRF protection)

Additional CSRF token not required because:
1. All state-changing operations require authenticated session cookie
2. SameSite=Lax prevents cross-origin form submissions
3. CORS policy restricts cross-origin API requests

---

## Input Validation

All user input validated via Pydantic schemas:

```python
class CreateShootout(BaseModel):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()
```

**Key rules:**
- Set reasonable limits (string length, file size)
- Sanitise filenames before using in paths
- Validate file types for uploads
- Never trust Content-Type headers for file validation

---

## Dependency Security

### Vulnerability Scanning

Run before every release and in CI:

```bash
# Python dependencies
docker compose exec backend pip-audit --strict

# NPM dependencies
docker compose --profile build exec astro npm audit --audit-level=high

# Secret detection
gitleaks detect --source . --config .gitleaks.toml --verbose
```

### Update Process

1. **Weekly:** Review dependabot PRs
2. **Monthly:** Run `pip-audit` and `npm audit`
3. **Before release:** Full security scan

**Update commands:**
```bash
# Update Python dependencies
docker compose exec backend pip install --upgrade <package>
# Then update requirements.txt

# Update NPM dependencies
docker compose --profile build exec astro pnpm update <package>
```

### Version Pinning

- Pin exact versions in production (`==` for Python, exact in package.json)
- Use ranges only for development dependencies
- Lock files committed: `requirements.txt`, `pnpm-lock.yaml`

---

## Secret Management

### Environment Variables

| Category | Location | Example |
|----------|----------|---------|
| **Development** | `.env` (gitignored) | `DB_PASSWORD=...` |
| **CI** | GitHub Secrets | Repository settings |
| **Production** | Platform secrets | Railway, Fly.io, etc. |

### Secret Categories

| Secret | Storage | Rotation |
|--------|---------|----------|
| Database password | Platform env | On breach |
| Session secret key | Platform env | On breach |
| T3K OAuth tokens | `.gts-auth.json` (600 perms) | Auto-refresh |

**Note:** T3K uses passwordless OAuth (email magic link). No client credentials stored.

### Auth File Security

The `.gts-auth.json` file stores OAuth tokens for development:
- Created with mode 0600 (owner read/write only)
- Permissions validated on every read
- Located in worktree parent directory (shared across worktrees)

```bash
# Verify permissions
ls -la $(dirname $(pwd))/.gts-auth.json
# Should show: -rw------- (600)
```

---

## Security Scanning Commands

Quick reference for security verification:

```bash
# Full security scan
docker compose exec backend pip-audit --strict
docker compose --profile build exec astro npm audit --audit-level=high
gitleaks detect --source . --config .gitleaks.toml --verbose

# Code security analysis
docker compose exec backend bandit -r app/ -ll -f txt

# Verify security headers
curl -I http://localhost:9000 | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport)"

# Check session cookie attributes
# (Inspect via browser DevTools > Application > Cookies)
```

---

## Security Review SLA

| Severity | Response Time | Examples |
|----------|---------------|----------|
| **Critical** | Same day | Auth bypass, RCE, SQLi, exposed secrets |
| **High** | 48 hours | XSS, CSRF, privilege escalation |
| **Medium** | 1 week | Information disclosure, weak crypto |
| **Low** | Next sprint | Missing headers, verbose errors |

**Escalation:** Critical vulnerabilities block all other work until resolved.

---

## Related

- [Authentication Rules](.claude/rules/authentication.md) - Session management, cookie security
- [Codebase Review Command](.claude/commands/codebase-review.md) - Security scanning workflow
