# Review Dimensions -- Detailed Checklists

## Code Quality

### Dead Code Detection

```bash
docker compose exec webapp vulture app/ --min-confidence 80
```

### Complexity Analysis

```bash
docker compose exec webapp radon cc app/ -s -a     # Cyclomatic complexity
docker compose exec webapp radon mi app/ -s         # Maintainability index
```

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Cyclomatic Complexity | <=5 | 6-10 | >10 |
| Maintainability Index | >65 | 40-65 | <40 |

### Test Coverage

```bash
docker compose exec webapp coverage run -m pytest /tests/unit/backend/ /tests/integration/backend/ -q --tb=no
docker compose exec webapp coverage report --skip-covered --fail-under=70
```

Minimum 70% coverage required.

### Manual Pattern Analysis

| Pattern | How to Find | Severity |
|---------|-------------|----------|
| Bare `except:` | `grep -rn "except:" apps/webapp/src/webapp/` | Medium |
| Magic numbers | Manual review | Low |
| N+1 queries | Check ORM usage in loops | Medium |
| Large functions (>50 lines) | `radon raw app/ -s` | Medium |
| Global state | `grep -rn "^[A-Z_].*=.*{" apps/webapp/src/webapp/` | Medium |

### Checklist

- [ ] Vulture shows no critical dead code
- [ ] No functions with CC >10
- [ ] Test coverage >=70%
- [ ] No bare `except:` blocks
- [ ] No N+1 query patterns
- [ ] All functions <50 lines (or documented exception)

---

## Security

### Static Analysis

```bash
docker compose exec webapp bandit -r app/ -ll -f txt
```

### Dependency Vulnerabilities

```bash
docker compose exec webapp pip-audit --strict
docker compose --profile build exec astro npm audit --audit-level=high
```

### Secret Detection

```bash
gitleaks detect --source . --config .gitleaks.toml --verbose
```

### Security Headers

```bash
curl -I http://localhost:9000 2>/dev/null | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport|Referrer-Policy|X-XSS)"
```

Expected: X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin.

### OWASP Top 10

| # | Category | Check |
|---|----------|-------|
| A01 | Injection | No f-strings in SQL, parameterised queries only |
| A02 | Broken Auth | Session cookies: httponly, secure, samesite=lax |
| A03 | Sensitive Data | No secrets in code, HTTPS enforced |
| A04 | XXE | No XML parsing of user input |
| A05 | Access Control | current_user checked, ownership verified |
| A06 | Misconfig | CSP headers, CORS restricted |
| A07 | XSS | Auto-escaping enabled, no `| safe` |
| A08 | Deserialization | Pydantic validates all input |
| A09 | Components | Dependency scans clean |
| A10 | Logging | Auth failures logged, no secrets in logs |

### Checklist

- [ ] Bandit: No HIGH findings
- [ ] pip-audit: No HIGH/CRITICAL vulnerabilities
- [ ] npm audit: No HIGH/CRITICAL vulnerabilities
- [ ] gitleaks: No secrets detected
- [ ] Security headers: All present
- [ ] OWASP A01-A10 verified

---

## Architecture

### Import Boundary Verification

```bash
uv run lint-imports
grep -r "sqlalchemy\|fastapi\|redis\|httpx" libs/core/ 2>/dev/null || echo "None found (good)"
grep -r "from source_" apps/webapp/ 2>/dev/null || echo "None found (good)"
```

### Aggregate Root Verification

```bash
grep -n "__eq__\|__hash__" libs/core/src/core/domain/entities/*.py
```

### Transaction Boundary Audit

| Layer | Transaction Method | Expected |
|-------|-------------------|----------|
| Services | `async with session.begin()` | Required |
| API Handlers | `session.begin()` | Forbidden |
| Adapters | `session.commit()` | Forbidden |
| Adapters | `session.flush()` | Allowed |

### SOLID Principles

| Principle | Verification | Severity |
|-----------|--------------|----------|
| SRP | One adapter per infrastructure concern | Medium |
| OCP | New adapter = new file, no service changes | Medium |
| LSP | All adapters return domain types | High |
| ISP | Ports have <=5 methods | Low |
| DIP | Services depend on Protocol, not concrete class | High |

### Checklist

- [ ] No import boundary violations
- [ ] All aggregate roots have __eq__ and __hash__
- [ ] Services use `async with session.begin()`
- [ ] API handlers don't start transactions
- [ ] Services depend on Ports (Protocol), not concrete Adapters

---

## Frontend

### Astro Sync

```bash
just verify-astro-sync
```

### data-astro-reload Audit

```bash
grep -E 'href="/(gear|shootouts|library|shootout|chain)' astro/src/components/Header.astro | grep -v 'data-astro-reload'
```

### data-testid Coverage

```bash
grep -rn 'hx-get\|hx-post\|hx-delete\|hx-put' astro/src/pages/ | grep -v 'data-testid'
grep -rn '<button' astro/src/pages/ | grep -v 'data-testid'
grep -rn '<input\|<select\|<textarea' astro/src/pages/ | grep -v 'data-testid'
```

### Checklist

- [ ] astro/dist/ in sync with astro/src/
- [ ] pnpm lint passes
- [ ] All SSR links have data-astro-reload
- [ ] All interactive elements have data-testid
- [ ] HTMX containers have loading skeletons
- [ ] Fragment templates match backend routes

---

## Documentation

### Drift Detection

```bash
just verify-docs
```

### AGENTS.md Accuracy

Verify documented paths exist and documented just commands exist.

### Checklist

- [ ] All paths in AGENTS.md exist
- [ ] All just commands documented actually exist
- [ ] All documented skills have SKILL.md files
- [ ] Wiki links resolve

---

## Observability

### Metrics

```bash
curl -s http://localhost:8000/metrics | head -20
curl -s http://localhost:8000/metrics | grep -E "^t3k_"
```

### Circuit Breaker

```bash
curl -s http://localhost:8000/health/circuit-breaker | jq .
```

Expected: Threshold=5, Recovery=30s.

### Structured Logging

Verify JSON logging and sensitive data filtering.

### Checklist

- [ ] Prometheus /metrics endpoint accessible
- [ ] Circuit breaker health endpoint working
- [ ] JSON logging enabled in production mode
- [ ] Sensitive data redacted in logs

---

## Workflow

### Just Commands

```bash
just --list
just check --dry-run
```

### Pre-commit Hooks

```bash
pre-commit --version
pre-commit run --all-files
```

### Checklist

- [ ] All key just commands work
- [ ] Pre-commit hooks configured and working
- [ ] GitHub Actions workflows present and valid
- [ ] worktree.py commands functional
