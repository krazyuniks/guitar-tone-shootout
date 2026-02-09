---
description: Comprehensive post-mortem review of a completed epic
allowed-tools: Bash(gh:*), Bash(git:*), Bash(python:*), Read, Grep, Glob, Write
argument-hint: "<epic-number>"
context: fork
---

# /epic-review - Epic Post-Mortem Review

Generate a comprehensive review of a completed epic with metrics, learnings, and recommendations.

## Usage

```
/epic-review 1
```

## Data Sources

Read ALL of the following before producing the review:

### Local Data
1. `.tasks/projects/guitar-tone-shootout/epics/E{n}/index.md` — epic definition and task status
2. `.tasks/projects/guitar-tone-shootout/epics/E{n}/tasks/T*.md` — all task files
3. `.tasks/projects/guitar-tone-shootout/epics/E{n}/logs/session_*.log` — session logs
4. `.tasks/projects/guitar-tone-shootout/epics/E{n}/logs/errors/` — error reports
5. `.tasks/projects/guitar-tone-shootout/epics/E{n}/health-report.md` — final health check
6. `.tasks/projects/guitar-tone-shootout/epics/E{n}/snapshots/T*.json` — test snapshots

### GitHub Data
```bash
gh issue view <epic-number> --repo krazyuniks/guitar-tone-shootout
gh api repos/krazyuniks/guitar-tone-shootout/issues/<epic-number>/sub_issues
gh pr list --repo krazyuniks/guitar-tone-shootout --state all --search "E<n>"
```

### Git Data
```bash
git log --oneline --since="<epic-start-date>" -- libs/ apps/ sources/ tests/
```

## Output Files

Write the review to:
- `.tasks/projects/guitar-tone-shootout/epics/E{n}/REVIEW.md` — human-readable review
- `.tasks/projects/guitar-tone-shootout/epics/E{n}/review-data.json` — machine-readable metrics

## REVIEW.md Structure

```markdown
# Epic Review: E{n} — {Title}

## 1. Traceability
PRD -> Epic -> Tasks -> Commits -> PR chain.
Link each artifact to its source.

## 2. Plan vs Execution
| Metric | Planned | Actual |
|--------|---------|--------|
| Tasks | N | N |
| Files created | N | N |
| Duration | - | Xh Ym |

## 3. Per-Task Metrics
| Task | Tests | State | Attempts | Bounces | Duration | Notes |
|------|-------|-------|----------|---------|----------|-------|
| T1 | 5 | complete | 1 | 0 | 5m | Clean |
| T26 | 42 | complete | 3 | 1 | 45m | Oversized |

Flag tasks with >15 tests or >3 retries. Suggest how to split.

## 4. Agent Effectiveness
- Test-author success rate (red gate pass on first try)
- Implementer success rate (green gate pass on first try)
- Bounce-back rate (test bugs caught post-impl)
- Average retries per task

## 5. Task Complexity Analysis
Flag oversized tasks and suggest splits based on:
- Test count (>15 is oversized)
- File count (>3 impl files is oversized)
- Layer crossing (repository + service + API in one task)

## 6. Infrastructure Issues
CSS hash staleness, Docker problems, Playwright availability, etc.
Parse from error logs and session logs.

## 7. Learnings
What should be promoted to:
- SKILL.md (testing patterns)
- Agent instructions (implementer.md, test-author.md)
- MEMORY.md (project-specific knowledge)
- Rules (.claude/rules/)

## 8. Recommendations (ranked by impact)
| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| 1 | ... | Low/Med/High | High |
```

## review-data.json Structure

```json
{
  "epic": { "number": 1, "title": "...", "task_count": 28 },
  "tasks": [
    {
      "id": "T1",
      "title": "...",
      "test_count": 5,
      "state": "complete",
      "attempts": 1,
      "bounces": 0,
      "files_created": ["libs/core/..."],
      "errors": []
    }
  ],
  "metrics": {
    "test_author_first_pass_rate": 0.85,
    "implementer_first_pass_rate": 0.75,
    "bounce_back_rate": 0.10,
    "avg_retries": 1.2,
    "oversized_tasks": ["T26"]
  }
}
```

## Graceful Degradation

- If structured logging (`STRUCTURED:` entries) is missing, fall back to regex parsing of text logs
- If GitHub is unavailable, skip traceability section and note the gap
- If session logs are missing, note gaps in per-task metrics
- If error logs are empty, note "no errors recorded" (good sign)

## After Writing the Review

Present a brief summary to the user with:
1. Key metrics (pass rates, bounce-back rate)
2. Top 3 recommendations
3. Oversized tasks that should be split next time

Then offer to discuss any section in detail.
