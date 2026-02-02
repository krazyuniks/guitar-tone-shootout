---
description: Claim a GitHub issue, create worktree, and start planning.
allowed-tools: Bash(gh:*), Bash(./worktree.py:*)
argument-hint: "<issue-number>"
---

# /claim - Claim Issue and Start Work

Assign a GitHub issue to yourself, create a worktree, and initialize planning.

## Usage

```
/claim <issue-number>
/claim 357
```

## Steps

1. **Verify issue is ready (not blocked):**
   ```bash
   gh issue view <number> --repo krazyuniks/guitar-tone-shootout --json state,title,labels
   ```

2. **Check if blocked:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:blocked" --json number | grep -q '"number":<number>'
   ```
   If blocked, warn the user and show what's blocking it.

3. **Assign to self:**
   ```bash
   gh issue edit <number> --add-assignee @me --repo krazyuniks/guitar-tone-shootout
   ```

4. **Create worktree:**
   ```bash
   ./worktree.py setup <number>
   ```

5. **Navigate to worktree:**
   ```bash
   cd ../<worktree-name>
   ```

6. **Run planning:**
   ```
   /ralph-hybrid-plan
   ```

## Flags

- `--force` - Claim even if blocked or assigned to someone else
- `--no-start` - Don't start Docker services
- `--skip-plan` - Don't run planning after setup
