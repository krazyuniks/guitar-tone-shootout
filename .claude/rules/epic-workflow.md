# Epic Workflow Rules

## Hard Constraints

- **Epics run via the TDD state machine.** NEVER manually read task files, explore the codebase, or dispatch sub-agents for epic tasks.
- **One command to start:** `just epic-start <epic_number>` (or `python scripts/run_epic.py run <epic_number>`)
- **One command to check status:** `just epic-status <epic_number>`
- **One command to debug:** `just debug E<epic_number>`

## What the State Machine Does

The TDD state machine (`run_epic.py`) handles everything:
- Reads tasks, resolves dependencies, determines execution order
- Dispatches agents with correct MCP configuration per task
- Runs TDD phases (red → green → refactor)
- Tracks state, retries failures, manages concurrency

## When Asked to "Run the Epic"

1. Run `just epic-start <number>` — that's it
2. Monitor output for failures
3. If failures occur, use `just retry E<number> T<task>` or `just debug E<number>`
4. Do NOT read task files yourself, do NOT explore the codebase, do NOT dispatch agents manually

## Anti-Patterns (NEVER DO THIS)

```bash
# BANNED — reading all task files manually
Read(.tasks/projects/.../tasks/T114.md)
Read(.tasks/projects/.../tasks/T115.md)
# ... reading 30 task files

# BANNED — dispatching sub-agents for tasks
Task(subagent_type="implementer", prompt="implement T114...")
Task(subagent_type="explore-codebase", prompt="explore webapp...")

# BANNED — using /epic skill when just epic-start exists
Skill(skill="epic", args="start 95")
```

## The Only Valid Approach

```bash
just epic-start 95    # Start the state machine
just epic-status 95   # Check progress
just debug E95        # Debug if needed
just retry E95 T114   # Retry a failed task
```
