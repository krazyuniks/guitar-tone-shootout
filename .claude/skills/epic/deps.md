---
name: deps
description: Show dependency graph, sub-issues, and parent for a GitHub issue.
argument-hint: "<issue-number>"
context: current
---

# /epic deps - Show Issue Dependencies

Display the full dependency and hierarchy graph for a specific GitHub issue.

## Usage

```
/epic deps <issue-number>
/epic deps 120
```

## Steps

1. **Get issue details:**
   ```bash
   gh issue view <number> --repo krazyuniks/guitar-tone-shootout \
     --json number,title,state,labels
   ```

2. **Check for parent issue:**
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<number>/sub_issue \
     --jq '{number: .parent_issue_number, title: .parent_issue_title}' 2>/dev/null
   ```
   If 404, the issue has no parent.

3. **Check for sub-issues (children):**
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<number>/sub_issues \
     --jq '.[] | {number, title, state}'
   ```
   If the result is non-empty, the issue is a parent.

4. **Find issues that BLOCK this one:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:open blocking:#<number>"
   ```

5. **Find issues BLOCKED BY this one:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:open blocked-by:#<number>"
   ```

## Output Format

```
Issue #120: Queue topology alignment
Status: Open
Parent: #125 Architecture Migration

Sub-issues (children):
  (none — this is a leaf issue, runnable as epic)

Blocked by (must complete first):
  #117 - Project structure migration [closed]

Blocks (waiting on this):
  #121 - Scheduler migration [open]

Dependency chain:
  #117 (closed) → #120 (this) → #121 (open) → #122

Recommendation: #120 is unblocked and ready to run.
```

If the issue is a parent (has sub-issues), note that it cannot be run directly — the user should run a child issue instead.
