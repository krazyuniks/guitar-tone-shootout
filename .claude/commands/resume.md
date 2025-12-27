# /resume - Resume from Session State

Load context from previous session and continue work.

## Workflow

1. **Read session state** from `dev/session-state.md`
2. **Load active task docs** from `dev/active/[task]/`
3. **Check git status** for pending changes
4. **Summarize current state** to user
5. **Identify next action** from documentation

## What to Read

1. `dev/session-state.md` - Overall state
2. `dev/EXECUTION-PLAN.md` - Architecture context
3. `dev/active/[task]/*-context.md` - Key decisions
4. `dev/active/[task]/*-tasks.md` - Remaining work

## Resume Report Template

```markdown
## Session Resume

**Branch:** [branch name]
**Task:** [current task]
**Status:** [status from session-state]

### Recent Progress
[From session-state.md]

### Pending Changes
[From git status]

### Next Actions
1. [First priority]
2. [Second priority]

### Key Context
[Important decisions or blockers]
```

## Usage

```
User: /resume
Claude: [Reads all context, provides resume report, ready to continue]
```

## Important

- Always start new sessions with /resume
- Ensures no context is lost
- Prevents duplicate work
- Maintains decision continuity
