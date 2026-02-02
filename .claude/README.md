# Claude Code Configuration

Claude Code customizations for the Guitar Tone Shootout project.

## Structure

```
.claude/
├── agents/          # Specialized agent personas
├── commands/        # Slash commands (/plan, /check, /merge, /resume)
├── hooks/           # Lifecycle hooks (sync on start)
├── skills/          # Domain knowledge (frontend, backend, testing, etc.)
├── rules/           # Codebase rules (security, container-execution)
└── settings.json    # Permissions & hook config
```

## Quick Start

1. **Start:** `./worktree.py setup <issue>` - Creates worktree, claims task
2. **Work:** Implement feature, run `just check`
3. **Finish:** `/merge` - Creates PR, auto-teardown on merge

## Key Commands

| Command | Purpose |
|---------|---------|
| `/plan` | Plan epics with iterative refinement |
| `/check` | Run quality gates |
| `/merge` | Run quality gates, browser test, create PR, merge to main |
| `/resume` | Resume from session state |

## Documentation

- **Workflow:** Run `./worktree.py start` to begin
- **Dev guide:** `AGENTS.md` (project root)
- **Skills:** `.claude/skills/*/SKILL.md`
