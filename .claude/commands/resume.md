---
description: Load context from previous session and continue work.
allowed-tools: Read, Bash(git:*), Bash(gh:*)
---

# /resume - Resume Session

Load context and continue work from previous session.

## Workflow

1. **Session state**: Read `.claude/session-state.md` for handoff
2. **GitHub context**: Check current branch for issue number
3. **Git status**: Check for uncommitted changes
4. **Summarize** and identify next action

## Priority Order

1. **Continue current work** - If on a feature branch, continue that issue
2. **Find ready work** - Run `/next-issue` to find unblocked issues
3. **Plan new work** - If nothing ready, run `/epic-plan`

## Commands

```bash
# Read session state handoff
cat .claude/session-state.md

# Get current branch and extract issue number
BRANCH=$(git branch --show-current)
ISSUE=$(echo "$BRANCH" | grep -oE '^[0-9]+' | head -1)

# If issue number found, get GitHub context
if [ -n "$ISSUE" ]; then
    gh issue view "$ISSUE" --repo krazyuniks/guitar-tone-shootout
fi

# Check git status
git status --short
```

## Output Format

```markdown
## Session Resume

**Branch:** 357/add-waveform
**Session State:** in_progress

### Previous Session Handoff
[summary from .claude/session-state.md]

### Current Work
**GitHub Issue:** #357 - Add audio waveform visualization
**Issue Status:** open

### Git Status
3 uncommitted changes

### Next Action
Continue implementing waveform component
```
