# T{number}: {title}

## Source
- Epic: E{epic_number}
- Generated: {timestamp}

## Status
- state: pending
- phase: -
- project: -
- locked_at: -

## Dependencies
- blocked_by: []
- blocks: []

## Acceptance Criteria

```yaml
criteria:
  - id: AC1
    description: "TODO: Add acceptance criteria"
    validation: "docker compose exec -T webapp pytest tests/ -k 'test_name' -v"
```

## Description

{issue_body}

## Scope

```yaml
allowed_paths:
  - "libs/**/*.py"
  - "apps/**/*.py"
forbidden_paths:
  - "tests/**"
```

## TDD Phase Commands (GTS Docker-first)

```bash
# Phase 1: Write tests
just tdd-test-phase {task_id}

# Phase 2: Verify tests fail
just tdd-red {task_id}

# Phase 3: Lock tests
just tdd-lock {task_id}

# Phase 4: Implement
just tdd-impl-phase {task_id}

# Phase 5: Validate
just tdd-complete {task_id}
```

## Outputs
- files_created: []
- files_modified: []
- validation_result:
