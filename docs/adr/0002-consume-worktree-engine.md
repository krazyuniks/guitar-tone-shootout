# ADR-0002: Consume the external worktree engine for per-branch dev stacks

- Status: accepted
- Date: 2026-06-29
- Related: GTS backlog unit WT-engine-consume

## Context

GTS carried an ad-hoc, ~11.3k-line in-repo worktree tool (`worktree.py` plus the `worktree/` package) that allocated ports, rendered compose/env, brought the stack up, ran the gate, and tore it down. Port and slot allocation is a host-level concern contended across every project and worktree on the machine, not a per-project one, and a standalone host-level worktree engine now owns it: it allocates a globally-unique slot and non-colliding host ports, creates and destroys the git worktree, and runs a project's own `provision`/`gate`/`teardown` hooks.

GTS remains a containerised per-branch-stack project: every feature worktree needs its own isolated Postgres, storage, and ports. That isolation is real and GTS-owned; the mechanism that allocates the contended host resources is not.

## Decision

GTS consumes the worktree engine the way it consumes any external development tool:

- **The engine's whole job** is slot/port allocation, git-worktree lifecycle, and invoking the project's opaque hooks. It knows nothing of Docker, compose, storage, migrations, or secrets.
- **GTS ships only the thin consumer surface**: `worktree.toml` (project id, services, and which services need an allocated host port) plus the three lifecycle hooks under `scripts/worktree/` that derive compose project, container names, volumes, subnet, storage binds, migrations, and env from the injected `WORKTREE_SLOT` and `WORKTREE_PORT_*` values.
- **No engine code lives in-repo.** The in-repo `worktree.py` and `worktree/` package are retired.
- **The repo stays runner-agnostic.** External SDLC/workflow runners may drive the engine (provision a worktree, run the gate, publish a PR), but GTS never hard-codes any particular runner; the repo's contract is the manifest, the hooks, and the `just check` gate.

## Consequences

- Host-resource contention (ports across many projects and worktrees on one host) is solved once, at the host level, by the engine - not re-solved per project.
- Feature development uses `worktree up gts <branch>` / `worktree gate` / `worktree down`; DEVELOPMENT.md documents the workflow.
- Any hook change is testable by hand with the same up/gate/down cycle a runner would drive; there is no runner-only path.
