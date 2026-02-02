---
description: Generate completion report for an epic.
allowed-tools: Bash(gh:*), Bash(git:*), Read, Grep
argument-hint: "<epic-number>"
context: fork
---

# /epic-report - Epic Completion Report

Generate a completion report for an epic.

## Usage

```
/epic-report 441
```

## Steps

1. **Get Epic Details:**
   ```bash
   gh issue view <epic-number> --repo krazyuniks/guitar-tone-shootout
   ```

2. **Find Related Issues:**
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<epic-number>/sub_issues
   ```

3. **Check for TODOs:**
   ```bash
   git diff main...HEAD --name-only | xargs grep -n "TODO:" 2>/dev/null
   ```

## Output Format

### 1. Epic Summary
- Title and objective
- Overall completion percentage

### 2. Stories Status Table
| Story | Title | Status | Notes |
|-------|-------|--------|-------|
| #442 | Story title | Complete | |

### 3. Blocking Issues
- TODOs found in code
- Failing tests
- Open dependencies

### 4. Next Steps
- Recommended follow-up actions
- Issues to create
