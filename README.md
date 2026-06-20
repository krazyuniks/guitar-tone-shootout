# Guitar Tone Shootout

A/B testing platform for guitar tones.

## Documentation

| What | Where |
|------|-------|
| Development setup | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Agent rules | [AGENTS.md](./AGENTS.md) |
| Technical architecture | [wiki/GTS-Technical-Architecture.md](../wiki/GTS-Technical-Architecture.md) |
| Reference architecture | [wiki/REFERENCE-ARCHITECTURE.md](../wiki/REFERENCE-ARCHITECTURE.md) |

## Agent Configuration Architecture

Six layers, loaded in order:

| Layer | Path | Loaded | Purpose |
|-------|------|--------|---------|
| Global preferences | `~/.claude/CLAUDE.md` | Always | British English, conventional commits, foundational principles |
| Project rules | `AGENTS.md` | Always | All GTS rules in one file |
| Bounded context | `model/*/CLAUDE.md`, `apps/*/CLAUDE.md` | When in subdir | Dependencies, key patterns, key files |
| Hooks | `.claude/hooks/` | On tool use | Deterministic enforcement (mock-gate, protect-config, infra-block) |
| Skills | `.claude/skills/` (7 project, 5 global) | On invocation | GTS-specific domain knowledge only |
| Memory | `~/.claude/projects/.../memory/MEMORY.md` | Always | Session-learned facts |

### Documentation Source of Truth

- **For humans**: Wiki (`GTS-Technical-Architecture.md`, `REFERENCE-ARCHITECTURE.md`)
- **For agents**: AGENTS.md + per-context CLAUDE.md + `gts-architecture` skill (13 reference files)
- AGENTS.md links to wiki for deep dives. No duplication.

### What We Decided NOT To Do

- **ChromaDB/RAG**: ~1,200 lines of config fits passive context. Not needed yet.
- **Future path**: FTS5 + MCP server (like Obsidian Knowledge Index) when scaling beyond context window.
- **Pipe-delimited compression** (Vercel style): Structured markdown is more maintainable for this project size.
- **Per-file lint hook**: Pre-commit (`prek` + ruff) handles linting at commit time. No Claude-visible lint rules.

### Cross-Agent Sync

- `agent-sync` copies `.claude/skills/` → `.agents/skills/` (Codex), `~/.gemini/skills/`, `~/.codex/skills/`
- `cod` wrapper runs `agent-sync --quiet` before every invocation
- `.agents/skills/` and `.gemini/skills/` are gitignored — derived, not source of truth
