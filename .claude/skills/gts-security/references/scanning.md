# Vulnerability Scanning

## Scanning Commands

```bash
# Python dependencies
docker compose exec webapp pip-audit --strict

# NPM dependencies
docker compose --profile build exec astro npm audit --audit-level=high

# Secret detection
gitleaks detect --source . --config .gitleaks.toml --verbose

# Code security analysis
docker compose exec webapp bandit -r app/ -ll -f txt
```

## Full Security Scan (one-liner)

```bash
docker compose exec webapp pip-audit --strict && \
docker compose --profile build exec astro npm audit --audit-level=high && \
gitleaks detect --source . --config .gitleaks.toml --verbose
```

## Header Verification

```bash
curl -I http://localhost:9000 | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport)"
```

## Session Cookie Verification

Inspect via browser DevTools > Application > Cookies.

## Security Review SLA

| Severity | Response Time | Examples |
|----------|---------------|----------|
| **Critical** | Same day | Auth bypass, RCE, SQLi, exposed secrets |
| **High** | 48 hours | XSS, CSRF, privilege escalation |
| **Medium** | 1 week | Information disclosure, weak crypto |
| **Low** | Next sprint | Missing headers, verbose errors |

**Escalation:** Critical vulnerabilities block all other work until resolved.
