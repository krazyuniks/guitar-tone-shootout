# Session Management and Security

## Session Cookie Configuration

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly` | `True` | Prevents JavaScript access (XSS protection) |
| `secure` | `True` in production | Cookie only sent over HTTPS |
| `samesite` | `lax` | Prevents CSRF on cross-site POST requests |

**Production vs Development:**
- Development: `secure=False` to allow HTTP
- Production: `secure=True` enforced (HTTPS required)

## Session Duration

- Session cookies: 7 days
- T3K tokens: depends on T3K refresh token validity
- Tokens auto-saved after each OAuth flow

## CSRF Protection

State-changing operations use the `SameSite=Lax` cookie attribute:
- GET requests: Cookie sent (allows normal navigation)
- Cross-origin POST/PUT/DELETE: Cookie NOT sent (CSRF protection)

For forms submitted via HTMX:
- HTMX requests include the session cookie automatically
- `hx-post`, `hx-put`, `hx-delete` are protected by SameSite

Additional CSRF token not required due to:
1. All state-changing operations require authenticated session cookie
2. SameSite=Lax prevents cross-origin form submissions
3. CORS policy restricts cross-origin API requests

## Security Headers

Security headers are configured in `nginx.conf.template`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer info |
| `Content-Security-Policy` | Report-only mode | XSS/injection defence |
| `Strict-Transport-Security` | Set via HTTPS detection | Forces HTTPS |

## Content Security Policy (CSP)

| Directive | Value | Rationale |
|-----------|-------|-----------|
| `default-src` | `'self'` | Only same-origin by default |
| `script-src` | `'self' 'unsafe-inline' https://unpkg.com` | Alpine.js requires inline, HTMX from CDN |
| `style-src` | `'self' 'unsafe-inline' https://fonts.googleapis.com` | Tailwind inline styles, Google Fonts |
| `font-src` | `'self' https://fonts.gstatic.com` | Google Fonts assets |
| `img-src` | `'self' data: https:` | Data URIs for inline images, external images |
| `connect-src` | `'self' ws: wss:` | API and WebSocket connections |
| `frame-ancestors` | `'none'` | Prevent embedding in iframes |

CSP is in **report-only mode** initially to identify violations without breaking functionality.

## Verification

```bash
curl -I http://localhost:9000 | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport)"
```
