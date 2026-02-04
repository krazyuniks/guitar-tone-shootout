# CLAUDE.md Additions

Add this section to your existing CLAUDE.md file:

---

## AI Development Workflow

This project uses an automated TDD workflow for feature development. See the [Wiki](https://github.com/krazyuniks/guitar-tone-shootout/wiki/AI-Development-Workflow) for full documentation.

### Quick Start

```bash
# Sync an epic from GitHub
just epic-sync 42

# Start orchestration
just epic-start 42

# Check status
just epic-status 42
```

### TDD Phases

Every task goes through 5 phases:

1. **Test**: Write tests from acceptance criteria (test-author agent)
2. **Red**: Verify tests fail
3. **Lock**: Snapshot test files
4. **Impl**: Make tests pass (implementer agent - cannot modify tests)
5. **Validate**: Verify completion (validator agent)

### Key Rules

1. **Tests are immutable** during implementation phase
2. **All state in `.tasks/`** - read index.md for current status
3. **Orchestrator is stateless** - exits and restarts with fresh context
4. **Validation required** - "complete" means all checks pass

### State Location

```
.tasks/projects/guitar-tone-shootout/epics/E{n}/
├── index.md      # Dependency graph, status table
├── tasks/        # Individual task specs
├── snapshots/    # Test file hashes (TDD enforcement)
└── logs/         # Execution logs
```

### Debugging

```bash
just debug E42        # Full report
just errors E42       # Recent errors
just health E42       # System health
just retry E42 T43    # Reset failed task
```

### Agents

| Agent | Role | Constraints |
|-------|------|-------------|
| orchestrator | Coordinates tasks | No implementation |
| test-author | Writes tests | No implementation files |
| implementer | Makes tests pass | No test files |
| validator | Verifies completion | Read-only |
