---
description: Comprehensive codebase review for security, dead code, complexity, and design patterns
allowed-tools: Bash(docker compose exec backend:*), Bash(docker compose exec astro:*), Bash(gh issue create:*)
argument-hint: "[--section=<name>] [--severity=<level>] [--no-issue]"
model: claude-opus-4-5-20251101
context: fork
agent: code-reviewer
---

# Comprehensive Codebase Review

A modular, comprehensive review workflow for the Guitar Tone Shootout codebase.

---

## Table of Contents

1. [Preflight Checks](#1-preflight-checks)
2. [Severity Levels & SLAs](#2-severity-levels--slas)
3. [Code Quality](#3-code-quality)
4. [Security](#4-security)
5. [Architecture](#5-architecture)
6. [Frontend](#6-frontend)
7. [Documentation](#7-documentation)
8. [Observability](#8-observability)
9. [Workflow](#9-workflow)
10. [Findings Format](#10-findings-format)
11. [Summary Dashboard](#11-summary-dashboard)

---

## 1. Preflight Checks

**Run these checks FIRST before any other review section.**

### 1.1 Docker Health Check

```bash
# Verify all services are running
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

# Expected: All services "Up" and "healthy"
# Required services: db, redis, backend, nginx, worker, scheduler
```

### 1.2 Build Profile Check

```bash
# Verify build profile is available for Astro container
docker compose --profile build ps astro

# If astro container needed but not running:
docker compose --profile build up -d astro
```

### 1.3 Backend Connectivity

```bash
# Verify backend is responding
curl -s http://localhost:8000/health | jq .

# Expected: {"status": "healthy", ...}
```

### 1.4 Install Analysis Tools

```bash
docker compose exec backend pip install vulture bandit radon pip-audit -q
```

### Preflight Checklist

```markdown
- [ ] All Docker services healthy (`docker compose ps`)
- [ ] Backend responding (`/health` endpoint)
- [ ] Build profile available (for Astro checks)
- [ ] Analysis tools installed
```

**⚠️ Do not proceed if preflight checks fail.** Fix infrastructure issues first.

---

## 2. Severity Levels & SLAs

### Severity Definitions

| Level | Definition | Examples |
|-------|------------|----------|
| **Critical** | Security vulnerabilities, data loss risk, system down | Auth bypass, RCE, SQLi, exposed secrets, DB corruption |
| **High** | Significant bugs, broken features, security risks | XSS, CSRF, privilege escalation, major feature broken |
| **Medium** | Degraded functionality, maintainability issues | N+1 queries, complexity >10, missing tests, tech debt |
| **Low** | Minor issues, code style, optimizations | Missing type hints, dead code, verbose errors |

### Response SLAs

| Severity | Response Time | Resolution Time | PR Blocking |
|----------|---------------|-----------------|-------------|
| **Critical** | Same day | 24 hours | YES - blocks merge |
| **High** | 48 hours | 1 week | YES - blocks merge |
| **Medium** | 1 week | 2 weeks | No |
| **Low** | Next sprint | As capacity allows | No |

### Escalation Rules

- **Critical findings:** Create P0 issue immediately, notify team lead
- **High findings:** Create P1 issue, include in sprint planning
- **Medium findings:** Create P2 issue, add to backlog
- **Low findings:** Create issue if pattern is widespread, else note in PR

---

## 3. Code Quality

**Can be run independently:** `--section=quality`

### 3.1 Dead Code Detection

Find unused functions, variables, and imports:

```bash
docker compose exec backend vulture app/ --min-confidence 80
```

**Severity:** Low (unless dead code is security-sensitive)

### 3.2 Complexity Analysis

Identify overly complex functions:

```bash
# Cyclomatic complexity
docker compose exec backend radon cc app/ -s -a

# Maintainability index
docker compose exec backend radon mi app/ -s
```

**Thresholds:**

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Cyclomatic Complexity | ≤5 | 6-10 | >10 |
| Maintainability Index | >65 | 40-65 | <40 |

### 3.3 Test Coverage

```bash
docker compose exec backend coverage run -m pytest /tests/unit/backend/ /tests/integration/backend/ -q --tb=no
docker compose exec backend coverage report --skip-covered --fail-under=70
```

**Threshold:** Minimum 70% coverage required.

### 3.4 Manual Pattern Analysis

Check for these anti-patterns:

| Pattern | How to Find | Severity |
|---------|-------------|----------|
| Bare `except:` | `grep -rn "except:" backend/app/` | Medium |
| Magic numbers | Manual review | Low |
| N+1 queries | Check ORM usage in loops | Medium |
| Large functions (>50 lines) | `radon raw app/ -s` | Medium |
| Global state | `grep -rn "^[A-Z_].*=.*{" backend/app/` | Medium |
| Missing type hints | `mypy --disallow-untyped-defs app/` | Low |

### Code Quality Checklist

```markdown
- [ ] Vulture shows no critical dead code
- [ ] No functions with CC >10
- [ ] Test coverage ≥70%
- [ ] No bare `except:` blocks
- [ ] No N+1 query patterns
- [ ] All functions <50 lines (or documented exception)
```

---

## 4. Security

**Can be run independently:** `--section=security`

### 4.1 Static Analysis (Bandit)

```bash
docker compose exec backend bandit -r app/ -ll -f txt
```

**Severity:** Findings are pre-classified by Bandit (High/Medium/Low).

### 4.2 Dependency Vulnerabilities

```bash
# Python dependencies
docker compose exec backend pip-audit --strict

# NPM dependencies (if astro container running)
docker compose --profile build exec astro npm audit --audit-level=high
```

**Severity:** HIGH/CRITICAL vulnerabilities are Critical severity.

### 4.3 Secret Detection

```bash
# Requires gitleaks on host
gitleaks detect --source . --config .gitleaks.toml --verbose
```

**Severity:** Exposed secrets are Critical.

### 4.4 Security Headers

```bash
curl -I http://localhost:9000 2>/dev/null | grep -E "(X-Frame|X-Content|Content-Security|Strict-Transport|Referrer-Policy|X-XSS)"
```

**Expected Headers:**

| Header | Expected Value |
|--------|----------------|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-XSS-Protection` | `1; mode=block` |
| `Content-Security-Policy-Report-Only` | `default-src 'self'; ...` |

### 4.5 OWASP Top 10 Manual Review

| # | Category | What to Check |
|---|----------|---------------|
| A01 | **Injection** | No f-strings in SQL, parameterised queries only |
| A02 | **Broken Auth** | Session cookies: `httponly`, `secure`, `samesite=lax` |
| A03 | **Sensitive Data** | No secrets in code, HTTPS enforced |
| A04 | **XXE** | No XML parsing of user input |
| A05 | **Access Control** | `current_user` checked, ownership verified |
| A06 | **Misconfig** | CSP headers, CORS restricted, admin blocked |
| A07 | **XSS** | Auto-escaping enabled, no `| safe` |
| A08 | **Deserialization** | Pydantic validates all input |
| A09 | **Components** | Dependency scans clean |
| A10 | **Logging** | Auth failures logged, no secrets in logs |

### Security Checklist

```markdown
- [ ] Bandit: No HIGH findings
- [ ] pip-audit: No HIGH/CRITICAL vulnerabilities
- [ ] npm audit: No HIGH/CRITICAL vulnerabilities
- [ ] gitleaks: No secrets detected
- [ ] Security headers: All present
- [ ] OWASP A01: Parameterised queries verified
- [ ] OWASP A02: Session cookies properly configured
- [ ] OWASP A05: Ownership checks on resources
- [ ] OWASP A07: Auto-escaping, no raw HTML
- [ ] OWASP A10: Auth events logged, no secrets in logs
```

---

## 5. Architecture

**Can be run independently:** `--section=architecture`

**Pattern Reference:** Load `software-architecture` skill for DDD, CQRS, and Hexagonal Architecture principles.

**Manual Review:** Use `/arch-review` for design decisions and pattern guidance.

### 5.1 Import Boundary Verification (Hexagonal Architecture)

**CRITICAL:** Domain layer must not import from outer layers.

```bash
# These should all return EMPTY - violations are critical
echo "=== Domain importing services (VIOLATION) ==="
grep -r "from app.services" backend/app/domain/ 2>/dev/null || echo "None found (good)"

echo "=== Domain importing adapters (VIOLATION) ==="
grep -r "from app.adapters" backend/app/domain/ 2>/dev/null || echo "None found (good)"

echo "=== Domain importing ORM models (VIOLATION) ==="
grep -r "from app.models" backend/app/domain/ 2>/dev/null || echo "None found (good)"

echo "=== Adapters importing services (VIOLATION) ==="
grep -r "from app.services" backend/app/adapters/ 2>/dev/null || echo "None found (good)"

echo "=== Adapters importing API (VIOLATION) ==="
grep -r "from app.api" backend/app/adapters/ 2>/dev/null || echo "None found (good)"
```

**Severity:** Import violations are High.

### 5.2 Aggregate Root Verification

```bash
# Verify aggregate roots have identity equality
grep -n "__eq__\|__hash__" backend/app/domain/entities/shootout.py
grep -n "__eq__\|__hash__" backend/app/domain/entities/signal_chain.py
grep -n "__eq__\|__hash__" backend/app/domain/entities/user.py
grep -n "__eq__\|__hash__" backend/app/domain/entities/t3k_pack.py
```

**Aggregate Roots:**

| Aggregate | File | Child Entities |
|-----------|------|----------------|
| Shootout | `domain/entities/shootout.py` | ToneSelections |
| SignalChain | `domain/entities/signal_chain.py` | SignalChainBlocks |
| User | `domain/entities/user.py` | - |
| T3KPack | `domain/entities/t3k_pack.py` | T3KModels |

### 5.3 Transaction Boundary Audit

```bash
# Services should use session.begin() or begin_nested()
grep -rn "async with.*session.begin" backend/app/services/ | head -10

# API handlers should NOT start transactions
grep -rn "session.begin" backend/app/api/ | grep -v "\.pyc"
# Should return empty

# Adapters should use flush(), not commit()
grep -rn "\.commit()" backend/app/adapters/
# Should return empty
```

**Pattern Check:**

| Layer | Transaction Method | Expected |
|-------|-------------------|----------|
| Services | `async with session.begin()` | ✓ Required |
| API Handlers | `session.begin()` | ✗ Forbidden |
| Adapters | `session.commit()` | ✗ Forbidden |
| Adapters | `session.flush()` | ✓ Allowed |

### 5.4 Bounded Context Audit

```bash
# Check for cross-context imports
grep -r "from app.domain.entities.shootout" backend/app/domain/entities/signal_chain.py
grep -r "from app.domain.entities.signal_chain" backend/app/domain/entities/shootout.py
# Should return empty
```

### 5.5 SOLID Principles Verification

```bash
# Dependency Inversion: Services should NOT directly instantiate adapters
echo "=== Services instantiating adapters directly (VIOLATION) ==="
grep -rn "SQLAlchemy.*Repository(" backend/app/services/ 2>/dev/null || echo "None found (good)"
grep -rn "= .*Adapter(" backend/app/services/ 2>/dev/null || echo "None found (good)"

# Interface Segregation: Ports should be minimal
echo "=== Port method counts ==="
for f in backend/app/domain/ports/*.py; do
  echo "$f: $(grep -c 'def ' "$f" 2>/dev/null || echo 0) methods"
done

# Open/Closed: New adapters should not modify services
echo "=== Recent adapter additions ==="
git log --oneline --name-only -10 | grep -E "adapters/.*\.py$" | head -5
```

**SOLID Compliance:**

| Principle | Verification | Severity |
|-----------|--------------|----------|
| **SRP** | One adapter per infrastructure concern | Medium |
| **OCP** | New adapter = new file, no service changes | Medium |
| **LSP** | All adapters return domain types | High |
| **ISP** | Ports have ≤5 methods | Low |
| **DIP** | Services depend on Protocol, not concrete class | High |

### Architecture Checklist

```markdown
## Hexagonal Architecture (Layer Boundaries)
- [ ] No import boundary violations (Domain→Services/Adapters/Models)
- [ ] Repository ports in domain/ports/, implementations in adapters/
- [ ] Adapters don't import services or API

## DDD Patterns
- [ ] All aggregate roots have __eq__ and __hash__
- [ ] Aggregates don't import other aggregates
- [ ] Value objects are immutable (@dataclass(frozen=True))

## Transaction Ownership
- [ ] Services use `async with session.begin()`
- [ ] API handlers don't start transactions
- [ ] Adapters use `flush()` not `commit()`

## SOLID Principles
- [ ] Services depend on Ports (Protocol), not concrete Adapters
- [ ] One adapter per infrastructure concern (SRP)
- [ ] Adding new adapter doesn't modify services (OCP)
```

**For pattern details:** See `software-architecture` skill

---

## 6. Frontend

**Can be run independently:** `--section=frontend`

### 6.1 Astro Sync Verification

```bash
just verify-astro-sync
```

**Severity:** Pre-bundled sync issues are High (CI will fail).

### 6.2 Frontend Lint & Type Check

```bash
docker compose --profile build up -d astro
docker compose --profile build exec astro pnpm lint
docker compose --profile build exec astro pnpm check
```

### 6.3 data-astro-reload Audit

Links from Astro pages to SSR pages MUST have `data-astro-reload`:

```bash
grep -E 'href="/(gear|shootouts|library|shootout|chain)' astro/src/components/Header.astro | grep -v 'data-astro-reload'
```

**SSR Routes requiring `data-astro-reload`:**
- `/gear`, `/gear/*`
- `/shootouts`
- `/library/*`
- `/shootout/*`
- `/chain/*`

**Severity:** Missing `data-astro-reload` is High (navigation breaks).

### 6.4 data-testid Coverage Audit

```bash
# HTMX containers missing data-testid
grep -rn 'hx-get\|hx-post\|hx-delete\|hx-put' astro/src/pages/ | grep -v 'data-testid'

# Buttons missing data-testid
grep -rn '<button' astro/src/pages/ | grep -v 'data-testid'

# Form inputs missing data-testid
grep -rn '<input\|<select\|<textarea' astro/src/pages/ | grep -v 'data-testid'
```

**Severity:** Missing test IDs are Medium (affects E2E tests).

### 6.5 HTMX Fragment Mapping Audit

```bash
# List all HTML fragment endpoints
grep -n '@router\.\(get\|post\|put\|delete\)' backend/app/api/v1/html.py | head -30

# List all fragment templates
ls -la astro/dist/fragments/
```

**Convention:** `/api/v1/html/{domain}/{action}` → `fragments/{domain}/{action}.html`

### Frontend Checklist

```markdown
- [ ] `astro/dist/` is in sync with `astro/src/`
- [ ] pnpm lint passes
- [ ] pnpm check passes
- [ ] All SSR links have `data-astro-reload`
- [ ] All interactive elements have `data-testid`
- [ ] Test IDs follow naming convention
- [ ] HTMX containers have loading skeletons
- [ ] Fragment templates match backend routes
- [ ] Design tokens from CSS variables (not hardcoded)
```

---

## 7. Documentation

**Can be run independently:** `--section=documentation`

### 7.1 Documentation Drift Detection

```bash
./scripts/check-docs.sh
# Or via just:
just verify-docs
```

### 7.2 AGENTS.md Accuracy

```bash
# Verify documented paths exist
grep -E "^\| \*\*" AGENTS.md | while read line; do
  path=$(echo "$line" | grep -oE "backend/[a-z/]+|astro/[a-z/]+")
  if [ -n "$path" ] && [ ! -d "$path" ]; then
    echo "Missing: $path"
  fi
done

# Verify documented just commands exist
grep -oE "just [a-z-]+" AGENTS.md | sort -u | while read cmd; do
  if ! just --list 2>/dev/null | grep -q "${cmd#just }"; then
    echo "Missing: $cmd"
  fi
done
```

### 7.3 Skill Accuracy

```bash
# List all skills
ls -la .claude/skills/*/SKILL.md

# Verify skill references in AGENTS.md match actual skills
grep -oE "\`[a-z-]+\`" AGENTS.md | tr -d '`' | sort -u | while read skill; do
  if [ -d ".claude/skills/$skill" ]; then
    echo "Found: $skill"
  fi
done
```

### 7.4 Wiki Sync Check

```bash
# Check wiki links in AGENTS.md resolve
grep -oE '\[.*\]\(https://github.com/.*/wiki/[^)]+\)' AGENTS.md | while read link; do
  page=$(echo "$link" | grep -oE 'wiki/[^)]+' | sed 's/wiki\///')
  echo "Wiki page: $page"
done
```

### Documentation Checklist

```markdown
- [ ] All paths in AGENTS.md exist
- [ ] All just commands documented actually exist
- [ ] All documented skills have SKILL.md files
- [ ] Wiki links resolve (spot check)
- [ ] DEVELOPMENT.md matches current architecture
- [ ] Docker versions in docs match docker-compose.yml
```

---

## 8. Observability

**Can be run independently:** `--section=observability`

### 8.1 Metrics Verification

```bash
# Check Prometheus metrics are exposed
curl -s http://localhost:8000/metrics | head -20

# Verify T3K metrics
curl -s http://localhost:8000/metrics | grep -E "^t3k_"

# Verify business metrics
curl -s http://localhost:8000/metrics | grep -E "^(daily_active_users|feature_usage|conversion_funnel)"

# Verify circuit breaker metrics
curl -s http://localhost:8000/metrics | grep -E "^t3k_circuit_breaker"
```

### 8.2 Circuit Breaker Verification

```bash
# Check circuit breaker health endpoint
curl -s http://localhost:8000/health/circuit-breaker | jq .

# Verify configuration
docker compose exec backend python -c "
from app.core.circuit_breaker import get_circuit_breaker
cb = get_circuit_breaker()
state = cb.get_state()
print(f'State: {state[\"state\"]}')
print(f'Threshold: {state[\"failure_threshold\"]}')
print(f'Recovery: {state[\"recovery_timeout\"]}s')
"
```

**Expected:** Threshold=5, Recovery=30s

### 8.3 Structured Logging Verification

```bash
# Check JSON logging
docker compose exec backend env LOG_FORMAT=json python -c "
from app.core.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test')
logger.info('Test message', extra={'key': 'value'})
"

# Verify sensitive data filtering
docker compose exec backend python -c "
from app.core.logging import sanitize_dict
print(sanitize_dict({'user': 'bob', 'password': 'secret123'}))
"
# Should show: {'user': 'bob', 'password': '[REDACTED]'}
```

### 8.4 Error Handling Verification

```bash
docker compose exec backend python -c "
from app.core.exceptions import *
print('AppException subclasses:')
for cls in [NotFoundError, BadRequestError, ValidationError, AuthenticationError,
            AuthorizationError, ConflictError, RateLimitError, ExternalServiceError,
            ServiceUnavailableError]:
    print(f'  {cls.__name__}: {cls.status_code} ({cls.code})')
"
```

### Observability Checklist

```markdown
- [ ] Prometheus /metrics endpoint accessible
- [ ] T3K sync metrics present
- [ ] Business metrics (DAU, feature usage) present
- [ ] Circuit breaker metrics present
- [ ] Circuit breaker health endpoint working
- [ ] Circuit breaker config correct (5 failures, 30s)
- [ ] JSON logging enabled in production mode
- [ ] Sensitive data redacted in logs
- [ ] Exception hierarchy consistent
- [ ] SLOs documented (99.9% availability, p95 <500ms)
```

---

## 9. Workflow

**Can be run independently:** `--section=workflow`

### 9.1 Just Commands Audit

```bash
# List all just commands
just --list

# Verify key commands work
just check --dry-run
just test-backend --dry-run
just test-e2e-quick --dry-run
```

### 9.2 Pre-commit Hooks

```bash
# Verify pre-commit is installed
pre-commit --version

# Check hook configuration
cat .pre-commit-config.yaml | head -30

# Run hooks manually
pre-commit run --all-files
```

### 9.3 CI Pipeline

```bash
# Check GitHub Actions workflows
ls -la .github/workflows/

# Verify workflow syntax (requires act)
# act -l
```

### 9.4 Worktree Setup

```bash
# Verify worktree.py commands
python worktree.py --help
python worktree.py auth-status
```

### Workflow Checklist

```markdown
- [ ] All key just commands work (check, test-*, build-astro)
- [ ] Pre-commit hooks configured and working
- [ ] GitHub Actions workflows present and valid
- [ ] worktree.py commands functional
- [ ] Auth persistence working across worktrees
- [ ] Hot reload working (just watch-astro)
```

---

## 10. Findings Format

Use this format for all findings to enable GitHub issue creation:

### Individual Finding Template

```markdown
### [SEVERITY] Title

**Location:** `file/path.py:line_number`
**Severity:** Critical | High | Medium | Low
**Category:** Security | Architecture | Code Quality | Frontend | Documentation | Observability | Workflow

**Description:**
Brief description of the issue.

**Evidence:**
```
Code snippet or command output showing the issue
```

**Impact:**
What could happen if not fixed.

**Recommendation:**
How to fix it.

**Effort:** Low (<1h) | Medium (1-4h) | High (4h+)
```

### GitHub Issue Format

```markdown
## Codebase Review: [Date]

### Executive Summary
- **Overall Status:** Healthy | Needs Attention | Critical Issues
- **Critical Findings:** X
- **High Findings:** X
- **Medium Findings:** X
- **Low Findings:** X

### Critical Findings (Blocking)
[List findings]

### High Findings (Blocking)
[List findings]

### Medium Findings (Non-blocking)
[List findings]

### Low Findings (Non-blocking)
[List findings]

### Quick Wins (<2h total)
[List easy fixes with high impact]

### Strengths
[What the codebase does well]

### Action Items
- [ ] Fix critical finding 1 (SLA: same day)
- [ ] Fix high finding 1 (SLA: 48h)
- [ ] Create ticket for medium findings
```

---

## 11. Summary Dashboard

After completing the review, fill in this dashboard:

```markdown
# Codebase Review Summary - [DATE]

## Preflight Status
| Check | Status |
|-------|--------|
| Docker Services | ✓/✗ |
| Backend Health | ✓/✗ |
| Build Profile | ✓/✗ |
| Tools Installed | ✓/✗ |

## Section Scores

| Section | Status | Critical | High | Medium | Low |
|---------|--------|----------|------|--------|-----|
| Code Quality | ✓/✗ | 0 | 0 | 0 | 0 |
| Security | ✓/✗ | 0 | 0 | 0 | 0 |
| Architecture | ✓/✗ | 0 | 0 | 0 | 0 |
| Frontend | ✓/✗ | 0 | 0 | 0 | 0 |
| Documentation | ✓/✗ | 0 | 0 | 0 | 0 |
| Observability | ✓/✗ | 0 | 0 | 0 | 0 |
| Workflow | ✓/✗ | 0 | 0 | 0 | 0 |

## Overall Health

| Metric | Value |
|--------|-------|
| **Test Coverage** | XX% |
| **Average Complexity** | X.X |
| **Open Vulnerabilities** | X |
| **Documentation Drift** | X items |

## SLA Status

| Severity | Count | SLA Met |
|----------|-------|---------|
| Critical | 0 | N/A |
| High | 0 | N/A |
| Medium | 0 | N/A |
| Low | 0 | N/A |

## Top Priorities

1. [Most urgent finding]
2. [Second most urgent]
3. [Third most urgent]

## Quick Wins

1. [Easy fix with impact]
2. [Easy fix with impact]
3. [Easy fix with impact]

## Strengths Noted

- [What's good about the codebase]
- [Another positive]
```

---

## Usage Examples

### Full Review

```bash
# Run complete review (all sections)
/codebase-review
```

### Section-Specific Review

```bash
# Security-focused review
/codebase-review --section=security

# Architecture review only
/codebase-review --section=architecture

# Frontend review only
/codebase-review --section=frontend
```

### By Severity

```bash
# Only report Critical and High findings
/codebase-review --severity=high
```

### Skip Issue Creation

```bash
# Review without creating GitHub issue
/codebase-review --no-issue
```

---

## Success Criteria

- [ ] Preflight checks pass
- [ ] All sections executed without errors
- [ ] Findings documented with severity and location
- [ ] SLAs assigned per severity
- [ ] Critical/High findings have immediate action items
- [ ] GitHub issue created (unless --no-issue)
- [ ] Summary dashboard completed
