# /epic - Unified Epic Lifecycle

This command is implemented by the `epic` skill.

See `.claude/skills/epic/SKILL.md` for the full workflow.

```
/epic                  # Show this help
/epic plan 70          # Plan epic (context -> gray areas -> goals -> tasks -> materialise)
/epic validate 70      # Pre-flight validation (check AC, scope, deps)
/epic fix 70           # Enrich sparse tasks (interactive)
/epic start 70         # Run TDD state machine
/epic status 70        # Show task states and blockers
```

## Subcommand Routing

Parse the argument after `/epic` to determine the subcommand:

| Input | Action |
|-------|--------|
| No args | Print this help |
| `plan {n}` | Run planning workflow (interactive) |
| `validate {n}` | Run `python scripts/validate_tasks.py {n}` |
| `fix {n}` | Interactive task enrichment |
| `start {n}` | Run `python scripts/run_epic.py run {n}` |
| `status {n}` | Run `python scripts/run_epic.py status {n}` |
