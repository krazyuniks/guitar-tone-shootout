---
description: Create PR, run CI-equivalent checks, enable auto-merge, monitor until merged.
allowed-tools: Bash(just:*), Bash(git:*), Bash(gh:*), Bash(docker compose:*)
---

# /merge - Create PR and Merge to Main

Single command to go from "done developing" to "merged".

## What This Does

1. **Sync** - Rebase on latest main
2. **Create PR** - With `Closes #ISSUE` linking
3. **Auto-merge** - Enable squash merge when CI passes
4. **Monitor CI** - Poll until merged or failed

CI is the gate. Pre-commit handles lint. No local test run required.

## Usage

```
/merge
```

## Why Not /pre-merge?

**Eliminated.** This command does everything /pre-merge did, plus creates the PR. No need for two separate commands.

## What Pre-commit Already Handled

Pre-commit auto-fixes on every commit:
- `ruff check --fix` (Python lint)
- `ruff format` (Python format)
- `frontend-lint --fix` (TypeScript lint)

**These are NOT re-run in /merge.** Trust pre-commit.

## Workflow

### Step 1: Sync with Remote

```bash
git fetch origin main
git rebase origin/main
git push --force-with-lease
```

If rebase conflicts, resolve and continue.

### Step 2: Pre-merge Checks (Optional)

```bash
just pre-merge  # Optional - CI will catch failures anyway
```

Runs CI-equivalent checks locally. **Skip if you trust CI as the gate.**

Use when:
- You want fast feedback before waiting for CI
- CI is flaky and you want to verify locally first

### Step 3: Create PR

```bash
# Get issue number from branch (e.g., "250/feature-name" → 250)
ISSUE=$(git branch --show-current | cut -d/ -f1)

gh pr create --repo krazyuniks/guitar-tone-shootout \
  --title "type(scope): Description" \
  --body "## Summary

Brief description of changes.

## Test plan

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E smoke tests pass

Closes #$ISSUE

---
🤖 Generated with [Claude Code](https://claude.ai/claude-code)"
```

### Step 4: Enable Auto-Merge

```bash
gh pr merge <number> --repo krazyuniks/guitar-tone-shootout --squash --auto
```

### Step 5: Monitor CI

Poll every 30 seconds until resolved:

```bash
gh pr checks <number> --repo krazyuniks/guitar-tone-shootout --watch
```

| State | Action |
|-------|--------|
| All pass | Auto-merge triggers, done |
| Any failure | Fix code, push, resume polling |
| Stuck | Check CI logs with `gh run view` |

## Issue Linking

**Every PR MUST include `Closes #ISSUE_NUMBER`.**

Get issue from branch: `git branch --show-current | cut -d/ -f1`

Example: Branch `250/feature-name` → Issue is `#250`

## After Merge

**Automatic.** The `merge-teardown` hook detects MERGED state and:
1. Closes the GitHub issue
2. Switches to main worktree
3. Runs `./worktree.py teardown`

No manual cleanup required.

## Quality Gates

| Gate | When | Purpose |
|------|------|---------|
| **Pre-commit** | On commit | Auto-fix lint/format |
| **`just pre-merge`** | Optional, before PR | Fast local feedback |
| **CI** | On PR | **The real gate** - blocks merge if failed |

CI is the enforcement mechanism. Local checks are optimizations.
