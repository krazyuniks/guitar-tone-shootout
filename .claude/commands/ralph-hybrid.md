# /ralph-hybrid - Usage Guide

Show Ralph Hybrid usage patterns and workflow guidance.

## Quick Reference

```
WORKFLOW: Plan → Run
```

| Step | Command | Where |
|------|---------|-------|
| 1. Setup (once per project) | `ralph-hybrid setup` | Terminal |
| 2. Create feature branch | `git checkout -b feature/xyz` | Terminal |
| 3. Plan the feature | `/ralph-hybrid-plan "description"` | Claude Code |
| 4. Run the loop | `ralph-hybrid run` | Terminal |

---

## Common Use Cases

### Starting a New Feature from a GitHub Issue

```bash
# 1. Create branch from issue (naming matters!)
git checkout -b 42-user-authentication

# 2. In Claude Code, plan the feature
/ralph-hybrid-plan

# Claude will auto-detect issue #42 and fetch context

# 3. Run the autonomous loop
ralph-hybrid run
```

### Starting a New Feature from Scratch

```bash
# 1. Create feature branch
git checkout -b feature/add-dark-mode

# 2. In Claude Code, plan with description
/ralph-hybrid-plan "Add dark mode toggle to settings"

# 3. After planning completes, run the loop
ralph-hybrid run
```

### Resuming Work on an Existing Feature

```bash
# 1. Switch to the feature branch
git checkout feature/add-dark-mode

# 2. Check status
ralph-hybrid status

# 3. Continue the loop
ralph-hybrid run
```

### Modifying Requirements Mid-Implementation

```
# In Claude Code, while ralph is NOT running:
/ralph-hybrid-amend
```

### Regenerating prd.json from Updated spec.md

```
# In Claude Code:
/ralph-hybrid-plan --regenerate
```

---

## Commands Summary

### Terminal Commands (`ralph-hybrid`)

| Command | Purpose |
|---------|---------|
| `ralph-hybrid setup` | Install Claude commands to project |
| `ralph-hybrid run [options]` | Execute the autonomous loop |
| `ralph-hybrid run --model opus` | Run with specific model |
| `ralph-hybrid status` | Show current feature progress |
| `ralph-hybrid validate` | Run preflight checks |
| `ralph-hybrid archive` | Archive completed feature |
| `ralph-hybrid import <file>` | Import PRD from Markdown/JSON |

### Claude Code Commands (slash commands)

| Command | Purpose |
|---------|---------|
| `/ralph-hybrid` | Show this usage guide |
| `/ralph-hybrid-plan` | Interactive planning workflow |
| `/ralph-hybrid-plan --regenerate` | Regenerate prd.json from spec.md |
| `/ralph-hybrid-amend` | Modify requirements during implementation |

---

## Key Concepts

### Fresh Context Per Iteration
Each `ralph-hybrid run` iteration starts Claude with a fresh context. Memory persists through:
- `prd.json` - Story completion state
- `progress.txt` - Append-only log
- Git history - Code changes

### Branch-Based Feature Folders
Feature files live in `.ralph-hybrid/{branch-name}/`:
```
.ralph-hybrid/
└── feature-42-user-auth/
    ├── spec.md         # Human-readable specification
    ├── prd.json        # Machine-readable stories
    ├── progress.txt    # Iteration log
    └── logs/           # Claude output per iteration
```

### The Two-Phase Workflow
1. **Planning** (`/ralph-hybrid-plan`) - Interactive, human-in-the-loop
2. **Execution** (`ralph-hybrid run`) - Autonomous, loop until complete

---

## Tips

- **Always plan first** - Don't skip `/ralph-hybrid-plan`, it creates the required files
- **Use descriptive branch names** - `42-user-auth` lets Ralph find GitHub issues
- **Check status often** - `ralph-hybrid status` shows completion progress
- **Archive when done** - `ralph-hybrid archive` cleans up completed work

---

## Troubleshooting

### "prd.json not found"
You haven't run `/ralph-hybrid-plan` yet. Run planning first.

### "Not on a feature branch"
Create a feature branch: `git checkout -b feature/your-feature`

### "Circuit breaker tripped"
Ralph detected no progress. Check `ralph-hybrid status` and logs.

### "Another instance running"
Use `ralph-hybrid kill` or wait for the other instance to finish.
