---
description: Mid-session save point. Commits WIP, pushes, and rebases on main.
allowed-tools: Bash(git:*)
---

# /checkpoint - Mid-Session Save Point

Checkpoint your work mid-session: commit, push, pull latest changes.

## When to Use

- Save progress during a long session
- Another worktree merged a PR and you want to pull it in
- Before starting a new task within the same session

## Steps

1. **Commit uncommitted changes** (if any):
   ```bash
   git add -A && git commit -m "WIP: checkpoint $(date +%H:%M)"
   ```

2. **Push to remote**:
   ```bash
   git push origin $(git branch --show-current)
   ```

3. **Rebase on latest main**:
   ```bash
   git fetch origin && git rebase origin/main
   ```

4. **Report status**:
   ```bash
   git log --oneline -3
   ```

## Notes

- WIP commits will be squashed before PR
- If rebase has conflicts, abort and notify user
- Safe to run anytime - idempotent
