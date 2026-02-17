# Claude Code Configuration

See [project README](../README.md) for configuration architecture.

## Structure

```
.claude/
├── hooks/           # Lifecycle hooks (deterministic enforcement)
├── skills/          # GTS-specific domain knowledge (7 skills)
├── rules/           # github.md (--repo flag reminder)
├── commands/        # Slash commands (/epic, /check, /merge, /resume)
└── settings.json    # Permissions & hook config
```
