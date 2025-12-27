# /worktree-list - List All Worktrees

Display all registered worktrees with their status.

## Usage

```
/worktree-list
```

## Output Format

```
┌─────────────────────────────────────────────────────────────────┐
│              Guitar Tone Shootout Worktrees                      │
├────────────────┬──────────┬─────────────────┬───────────────────┤
│ Name           │ Status   │ Ports           │ URL               │
├────────────────┼──────────┼─────────────────┼───────────────────┤
│ main (current) │ ● active │ 4321/8000/5432  │ http://localhost:4321 │
│ 42-feature     │ ● active │ 4331/8010/5433  │ http://localhost:4331 │
└────────────────┴──────────┴─────────────────┴───────────────────┘
```

## Legend

- `●` (green) - All containers running and healthy
- `○` (yellow) - Some containers down or unhealthy
- `(current)` - You are in this worktree

## Commands Executed

```bash
./worktree.py list
```

## Related Commands

- `/worktree-status` - Detailed status of current worktree
- `/worktree-ports` - Show all port allocations
