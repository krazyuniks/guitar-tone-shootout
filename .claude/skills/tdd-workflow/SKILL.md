---
name: tdd-workflow
description: TDD workflow orchestration for GitHub epics
triggers:
  - epic
  - tdd
  - task workflow
  - implement feature
  - orchestrate
---

# TDD Workflow Skill

Automated Test-Driven Development workflow with GitHub Epic synchronisation.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `just epic-sync 42` | Sync epic from GitHub |
| `just epic-start 42` | Begin orchestration |
| `just epic-status 42` | Check status |
| `just tdd-complete E42-T43` | Full task validation |

## Workflow Overview

1. **Sync**: Pull epic from GitHub to `.tasks/`
2. **Orchestrate**: Execute tasks in dependency order
3. **TDD Phases**: test → red → lock → impl → validate
4. **Push**: Update GitHub with completion status

## TDD Phases

### Phase 1: Test Specification
- Agent: `test-author`
- Write tests from acceptance criteria
- Tests MUST fail

### Phase 2: Red Verification
- Run: `just tdd-red {task_id}`
- Verify all tests fail (not error)

### Phase 3: Lock
- Run: `just tdd-lock {task_id}`
- Snapshot test files
- Commit with `test-lock:` prefix

### Phase 4: Implementation
- Agent: `implementer`
- Make tests pass
- CANNOT modify test files

### Phase 5: Validation
- Agent: `validator`
- Verify: tests pass + unchanged + quality + E2E

## State Location

```
.tasks/projects/guitar-tone-shootout/epics/E{n}/
├── index.md      # Status, dependency graph
├── tasks/        # Task specs
├── snapshots/    # Test file hashes
└── logs/         # Execution logs
```

## Debugging

```bash
just debug E42        # Full report
just errors E42       # Recent errors
just health E42       # System health
```

## Key Rules

1. **Tests are immutable** during implementation
2. **Orchestrator is stateless** - exits and restarts
3. **All state in `.tasks/`** - survives context loss
4. **Validation required** - "complete" means verified
5. **Use `just` commands** - never direct `python scripts/...` calls (see `.claude/rules/container-execution.md`)
