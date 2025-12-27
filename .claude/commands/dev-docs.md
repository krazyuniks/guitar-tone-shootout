# /dev-docs - Create Development Documentation

Generate comprehensive development documentation for a task.

## Workflow

1. **Analyze the current task/plan** from conversation context
2. **Create three files** in `dev/active/[task-name]/`:
   - `[task-name]-plan.md` - Strategic plan with phases
   - `[task-name]-context.md` - Key files and decisions
   - `[task-name]-tasks.md` - Actionable checklist

3. **Update `dev/session-state.md`** with task reference

## File Templates

### plan.md

```markdown
# [Task Name] - Implementation Plan

**Epic:** [Link to GitHub issue]
**Status:** In Progress
**Created:** [Date]

## Objective

[Clear statement of what we're building and why]

## Phases

### Phase 1: [Name]
- [ ] Task 1
- [ ] Task 2

### Phase 2: [Name]
- [ ] Task 1
- [ ] Task 2

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ... | ... | ... |

## Success Criteria

- [ ] Criteria 1
- [ ] Criteria 2
```

### context.md

```markdown
# [Task Name] - Context

## Key Files

| File | Purpose |
|------|---------|
| `path/to/file` | Description |

## Architecture Decisions

### Decision 1: [Title]
**Status:** Decided
**Context:** [Why this decision was needed]
**Decision:** [What we decided]
**Consequences:** [What this means]

## Dependencies

- External: [APIs, services]
- Internal: [Other tasks, modules]
```

### tasks.md

```markdown
# [Task Name] - Task Checklist

## Current Sprint

- [ ] Task 1
  - [ ] Subtask 1a
  - [ ] Subtask 1b
- [ ] Task 2

## Completed

- [x] Completed task 1
- [x] Completed task 2

## Blocked

- [ ] Blocked task (reason)
```

## Usage

```
User: /dev-docs
Claude: [Creates documentation based on current context]

User: /dev-docs fastapi-auth
Claude: [Creates dev/active/fastapi-auth/ documentation]
```

## Important

- Always update `dev/session-state.md` after creating docs
- Keep docs in sync with actual progress
- Archive to `dev/archive/` when task completes
