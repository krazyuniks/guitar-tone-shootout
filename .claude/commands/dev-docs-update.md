# /dev-docs-update - Update Development Documentation

Update session state and task documentation with current progress.

## Workflow

1. **Read current session state** from `dev/session-state.md`
2. **Identify active task** from context or prompt
3. **Update documentation**:
   - Mark completed items in tasks.md
   - Add new decisions to context.md
   - Update progress notes in session-state.md
4. **Note next actions** for session continuity

## When to Use

- Before ending a session
- After completing a phase
- When making significant decisions
- Before context compaction (/compact)

## Session State Template

Update `dev/session-state.md` with:

```markdown
# Session State

**Last Updated:** [Timestamp]
**Branch:** [current branch]

## Current Focus

[Task name and brief description]

## Active Work

| Task | Status | Next Action |
|------|--------|-------------|
| [Task] | [Status] | [Action] |

## Recent Progress

- [Date]: [What was done]
- [Date]: [What was done]

## Blockers

- [Any blockers or issues]

## Context for Next Session

[What the next session needs to know to continue]
```

## Usage

```
User: /dev-docs-update
Claude: [Updates session-state.md and active task docs]

User: /dev-docs-update "completed auth flow"
Claude: [Updates docs with auth flow completion]
```

## Important

- Run before ending every significant session
- Captures decisions that aren't in code
- Enables seamless session handoff
