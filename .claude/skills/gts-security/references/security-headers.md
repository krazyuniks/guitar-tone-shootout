# Security Headers

Security headers are configured in `nginx.conf.template`.

## Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer info |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS protection |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS (production) |

## Content Security Policy (CSP)

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

## Verification

```bash
curl -I http://localhost:9000 | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport)"
```

## Related

For CSRF and cookie security, see `gts-auth/references/session-mgmt.md`.
