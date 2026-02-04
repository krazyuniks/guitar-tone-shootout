# T{number}: {title}

## Source
- GitHub: https://github.com/krazyuniks/guitar-tone-shootout/issues/{number}
- Epic: E{epic_number}
- Synced: {timestamp}

## Status
- state: pending
- phase: -
- locked_at: -

## Dependencies
- blocked_by: []
- blocks: []

## Acceptance Criteria

```yaml
criteria:
  - id: AC1
    description: "TODO: Add acceptance criteria"
    validation: "echo 'TODO: Add validation command'"
```

## Description

{issue_body}

## Scope

```yaml
allowed_paths:
  - "TODO: Add implementation paths"
forbidden_paths:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.test.py"
```

## TDD Phase Commands

```bash
# Phase 1: Write tests
just tdd-test {task_id}

# Phase 2: Verify tests fail
just tdd-red {task_id}

# Phase 3: Lock tests
just tdd-lock {task_id}

# Phase 4: Implement
just tdd-impl {task_id}

# Phase 5: Validate
just tdd-complete {task_id}
```

## Outputs
- files_created: []
- files_modified: []
- validation_result:
