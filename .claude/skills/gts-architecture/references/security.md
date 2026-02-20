# Security

Security architecture following OWASP guidelines.

## Authentication

Delegated to external identity providers via OAuth 2.1:

| Aspect | Approach |
|--------|----------|
| **Flow** | Authorization code + PKCE (S256) |
| **Credential storage** | None -- IdP manages all credentials |
| **GTS responsibility** | Validate OAuth callback, issue token |
| **Providers** | Configurable (T3K, Google, GitHub, etc.) |

Token-based authentication (stateless):

| Aspect | Approach |
|--------|----------|
| **Token storage** | `.gts-auth.json` file (shared across worktrees) |
| **Token transfer** | Browser login, token copied to server via scp |
| **Validation** | Stateless token validation on each request |
| **No sessions** | No server-side session state |

GTS stores only the user's identity (ID, email, display name) and encrypted OAuth tokens in the auth file.

## Authorisation

Write-path protection -- users can only modify their own resources:

| Resource | Read Access | Write Access |
|----------|-------------|--------------|
| Shootouts | Public | Owner only |
| Audio segments | Public | Owner only |
| Signal chains | Public | Owner only |
| DI tracks | Public or private (user choice) | Owner only |

Implementation:
- Write operations filter by `user_id`
- Error responses return 404 for unauthorised writes (no existence leakage)
- Admin APIs network-isolated (no authentication layer)

## Transport Security

| Layer | Requirement |
|-------|-------------|
| TLS | 1.2 minimum, 1.3 preferred |
| HSTS | Enabled in production |
| Certificate | Managed by reverse proxy |

## Input Validation

All user input validated at API boundaries:

| Layer | Mechanism |
|-------|-----------|
| **API schemas** | Pydantic models with constraints |
| **Database** | SQLAlchemy ORM (parameterised queries) |
| **File uploads** | Type validation, size limits, sanitised names |

## Output Encoding

XSS prevention via auto-escaping:

| Template engine | Auto-escaping | Avoid |
|-----------------|---------------|-------|
| Jinja2 | Enabled | `| safe` filter |
| Astro | Enabled | `set:html` |
| React | Enabled | `dangerouslySetInnerHTML` |

## Security Headers

Configured at reverse proxy:

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | Restrictive policy |
| `X-Frame-Options` | DENY |
| `X-Content-Type-Options` | nosniff |
| `Referrer-Policy` | strict-origin-when-cross-origin |
| `Strict-Transport-Security` | max-age=31536000; includeSubDomains |

## Secret Management

| Category | Storage |
|----------|---------|
| Database credentials | Environment variables |
| Session secret | Environment variables |
| OAuth client ID/secret | Environment variables |

Rules:
- No secrets in source control or logs
- Environment-specific configuration

## Dependency Security

| Tool | Scope | Frequency |
|------|-------|-----------|
| `pip-audit` | Python dependencies | CI + weekly |
| `npm audit` | Node dependencies | CI + weekly |
| `gitleaks` | Secret detection | Pre-commit + CI |

## Audit Trail

Security events logged:

| Event | Logged Data |
|-------|-------------|
| Authentication success/failure | Provider, timestamp |
| Authorisation failure | User ID, resource, action |
