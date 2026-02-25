---
description: Show current session state - git, docker, and issue status.
allowed-tools: Bash(git:*), Bash(docker compose:*), Bash(gh:*), Bash(pwd)
---

# /status - Session State

Show the current development session state at a glance.

## When to Use

- Orienting after resuming work
- Checking environment health before a PR
- Understanding git state relative to main

## Commands

```bash
# Location
pwd
git branch --show-current

# Git state
git status --short
git rev-list --count HEAD..origin/main 2>/dev/null || echo "0"   # behind main
git rev-list --count origin/main..HEAD 2>/dev/null || echo "0"   # ahead of main

# GitHub issue (from branch name)
BRANCH=$(git branch --show-current)
ISSUE=$(echo "$BRANCH" | grep -oE '^[0-9]+' | head -1)
if [ -n "$ISSUE" ]; then
    gh issue view "$ISSUE" --repo krazyuniks/guitar-tone-shootout --json title,state
fi

# Docker services
docker compose ps --format json

# Backup status
ls -lt ../backups/*.dump 2>/dev/null | head -5
```

## Output Format

```markdown
## Session Status

### Location
- **Branch:** feature/issue-42
- **Tracking:** origin/feature/issue-42 (up to date)

### Active Work
- **GitHub Issue:** #42 - Title
- **Status:** open

### Git State
- Uncommitted changes: 3 files
- Ahead of main: 2 commits

### Environment
| Service | Status |
|---------|--------|
| frontend | healthy |
| backend | healthy |
| db | healthy |

### Backups
| Database | Last Backup | Age |
|----------|-------------|-----|
| gts_core | 20260217_1000 | 2h |

### Next Actions
[Contextual suggestions based on current state]
```

## Suggested Actions

| Condition | Suggestion |
|-----------|------------|
| Uncommitted changes | "X files need committing" |
| Behind main | "Consider rebasing" |
| No active issue | "Run `/epic next`" |
| Services stopped | "Start: `docker compose up -d`" |
| Clean + ahead | "Ready to `/merge`" |
