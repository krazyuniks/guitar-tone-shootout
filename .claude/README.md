# Claude Code Configuration

This directory contains Claude Code customizations for the Guitar Tone Shootout project.

## Structure

```
.claude/
├── agents/              # Specialized agent personas
│   ├── code-reviewer.md
│   ├── plan-reviewer.md
│   ├── error-resolver.md
│   └── documentation-writer.md
├── commands/            # Slash commands
│   ├── dev-docs.md
│   ├── dev-docs-update.md
│   ├── check.md
│   ├── resume.md
│   └── arch-review.md
├── hooks/               # Lifecycle hooks
│   ├── skill-activation.sh   # UserPromptSubmit: Suggest skills
│   └── quality-check.sh      # PostToolUse: Suggest checks
├── skills/              # Domain knowledge packs
│   ├── backend-dev/     # FastAPI + SQLAlchemy patterns
│   ├── frontend-dev/    # Astro + React + TanStack patterns
│   ├── playwright/      # E2E testing & debugging
│   ├── pipeline-dev/    # Audio/video processing
│   ├── testing/         # pytest patterns
│   ├── docker-infra/    # Docker & deployment
│   └── skill-writer/    # Meta-skill for creating skills
├── rules/               # Codebase rules
│   └── security.md      # Security guidelines
├── cache/               # Session caches (gitignored)
├── skill-rules.json     # Auto-activation configuration
├── settings.json        # Permissions & hooks
└── README.md            # This file
```

## Features

### Skills Auto-Activation

Skills are automatically suggested based on:
- Keywords in your prompt
- File content patterns
- File path matching

Configuration in `skill-rules.json`. Activation via `hooks/skill-activation.sh`.

### Slash Commands

| Command | Purpose |
|---------|---------|
| `/dev-docs` | Create task documentation |
| `/dev-docs-update` | Update session state |
| `/check` | Run quality gates |
| `/resume` | Resume from session state |
| `/arch-review` | Architecture review |

### Agents

Use with Task tool for specialized work:
- `code-reviewer` - Code quality review
- `plan-reviewer` - Plan validation
- `error-resolver` - Fix build/lint errors
- `documentation-writer` - Create docs

### Hooks

| Hook | Trigger | Action |
|------|---------|--------|
| skill-activation | UserPromptSubmit | Suggest relevant skills |
| quality-check | Edit/Write | Suggest running checks |

## Best Practices

1. **Start sessions with `/resume`** to load context
2. **End sessions with `/dev-docs-update`** to save state
3. **Run `/check`** before creating PRs
4. **Use skills** for domain-specific patterns

## Customization

### Adding a Skill

1. Create directory: `.claude/skills/[name]/`
2. Create `SKILL.md` with instructions
3. Add to `skill-rules.json` for auto-activation

### Adding a Command

1. Create `.claude/commands/[name].md`
2. Define workflow and usage

### Adding an Agent

1. Create `.claude/agents/[name].md`
2. Define role, process, and output format

## References

- [Claude Code Docs](https://docs.anthropic.com/claude-code)
- [Agent Skills Spec](https://agentskills.io)
- [AGENTS.md](../AGENTS.md) - Project workflow guide
