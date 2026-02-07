---
name: codebase-review
description: Comprehensive codebase review for security, dead code, complexity, and design patterns
---

# Codebase Review Skill

**Activation:** Codebase review, security audit, architecture review, code quality assessment

**Arguments:** `[--section=<name>] [--severity=<level>] [--no-issue]`

## Preflight Checks

Run these FIRST before any review section:

1. **Docker Health:** `docker compose ps` -- all services "Up" and "healthy"
2. **Build Profile:** `docker compose --profile build ps astro`
3. **Backend Health:** `curl -s http://localhost:8000/health | jq .`
4. **Install Tools:** `docker compose exec webapp pip install vulture bandit radon pip-audit -q`

Do not proceed if preflight checks fail.

## Review Sections

Each section can be run independently with `--section=<name>`.

| Section | Flag | Purpose |
|---------|------|---------|
| Code Quality | `--section=quality` | Dead code, complexity, test coverage |
| Security | `--section=security` | Bandit, pip-audit, OWASP, headers |
| Architecture | `--section=architecture` | Import boundaries, DDD, SOLID |
| Frontend | `--section=frontend` | Astro sync, data-testid, HTMX |
| Documentation | `--section=documentation` | Drift detection, AGENTS.md accuracy |
| Observability | `--section=observability` | Metrics, circuit breaker, logging |
| Workflow | `--section=workflow` | Just commands, pre-commit, CI |

See `references/review-dimensions.md` for detailed checklists per section.

## Severity Levels

| Level | Definition | Response SLA |
|-------|------------|--------------|
| **Critical** | Security vulnerabilities, data loss risk | Same day |
| **High** | Significant bugs, broken features | 48 hours |
| **Medium** | Degraded functionality, maintainability | 1 week |
| **Low** | Minor issues, code style | Next sprint |

Critical and High findings block PR merges.

## Workflow

1. Run preflight checks
2. Execute selected sections (or all)
3. Document findings using the template in `references/report-template.md`
4. Create GitHub issue (unless `--no-issue`)
5. Fill in summary dashboard

## Reference Files

| File | Purpose |
|------|---------|
| `references/review-dimensions.md` | Detailed checklists for each review section |
| `references/report-template.md` | Output format, findings template, summary dashboard |
| `references/gts-specifics.md` | GTS-specific review patterns and commands |
