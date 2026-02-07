# Report Template and Scoring

## Individual Finding Template

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

## GitHub Issue Format

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

## Summary Dashboard

```markdown
# Codebase Review Summary - [DATE]

## Preflight Status
| Check | Status |
|-------|--------|
| Docker Services | OK/FAIL |
| Backend Health | OK/FAIL |
| Build Profile | OK/FAIL |
| Tools Installed | OK/FAIL |

## Section Scores

| Section | Status | Critical | High | Medium | Low |
|---------|--------|----------|------|--------|-----|
| Code Quality | OK/FAIL | 0 | 0 | 0 | 0 |
| Security | OK/FAIL | 0 | 0 | 0 | 0 |
| Architecture | OK/FAIL | 0 | 0 | 0 | 0 |
| Frontend | OK/FAIL | 0 | 0 | 0 | 0 |
| Documentation | OK/FAIL | 0 | 0 | 0 | 0 |
| Observability | OK/FAIL | 0 | 0 | 0 | 0 |
| Workflow | OK/FAIL | 0 | 0 | 0 | 0 |

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

## Severity Response SLAs

| Severity | Response Time | Resolution Time | PR Blocking |
|----------|---------------|-----------------|-------------|
| Critical | Same day | 24 hours | YES |
| High | 48 hours | 1 week | YES |
| Medium | 1 week | 2 weeks | No |
| Low | Next sprint | As capacity allows | No |

## Escalation Rules

- **Critical:** Create P0 issue immediately, notify team lead
- **High:** Create P1 issue, include in sprint planning
- **Medium:** Create P2 issue, add to backlog
- **Low:** Note in PR if pattern is widespread

## Success Criteria

- [ ] Preflight checks pass
- [ ] All sections executed without errors
- [ ] Findings documented with severity and location
- [ ] SLAs assigned per severity
- [ ] Critical/High findings have immediate action items
- [ ] GitHub issue created (unless --no-issue)
- [ ] Summary dashboard completed
