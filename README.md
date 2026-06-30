# Guitar Tone Shootout

A/B testing platform for guitar tones.

## Documentation

| What | Where |
|------|-------|
| Development setup | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Agent rules | [AGENTS.md](./AGENTS.md) |
| Technical architecture | [wiki/GTS-Technical-Architecture.md](../wiki/GTS-Technical-Architecture.md) |
| Reference architecture | [wiki/REFERENCE-ARCHITECTURE.md](../wiki/REFERENCE-ARCHITECTURE.md) |

## Current Operating Model

- Use `just --list` for commands; project code runs in Docker through `just`.
- Feature work runs in engine-provisioned worktrees under `~/Work/guitar-tone-worktrees/`.
- CI runs on PRs and `main`; the worktree gate remains the fuller local quality gate.
- `AGENTS.md` is the project agent doctrine. `.claude/` contains tracked Claude hooks, commands, and skills. `.woof/*.toml` is the tracked consumer configuration for the future woof runner.
- `.agents/`, `.gemini/`, `.planning/`, and `.vf-runs/` are ignored derived/run artefacts, not project memory.
