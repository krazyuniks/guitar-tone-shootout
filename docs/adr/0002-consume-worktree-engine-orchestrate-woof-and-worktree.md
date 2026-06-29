# ADR-0002: Consume the worktree engine; orchestrate woof and worktree from GTS's PM layer

- Status: accepted
- Date: 2026-06-29
- Related: worktree engine ADR-0010 (thin resource coordinator); VF ADR-010 (VaultForeman absorbed into Woof); GTS epic WT-engine-consume (`planning/worktree-engine-consumption.md`)

## Context

GTS carries an ad-hoc, ~11.3k-line in-repo worktree tool (`worktree.py` plus the `worktree/` package) that allocates ports, renders compose/env, brings the stack up, runs the gate, and tears it down. It duplicates two concerns that now exist as standalone tools:

- a **host-level worktree engine** (`~/Work/worktree`, worktree-engine ADR-0010) that allocates the global slot and host ports, creates the git worktree, and runs a project's own `provision`/`gate`/`teardown`; and
- **Woof**, the SDLC engine that drives a work unit through produce/gate/review/merge.

GTS is also a containerised per-branch-stack project: every feature worktree needs its own isolated Postgres, storage, and ports. That isolation is real and GTS-owned; the mechanism that allocates the contended host resources (ports above all) is not.

## Decision

GTS consumes both tools the way it consumes any external tool, and composes them from its own PM/orchestration layer. Three independent layers, with a sharp boundary between them:

- **worktree** (host tool). Allocates the global slot and host ports, creates and destroys the git worktree, and calls the project's `provision`/`gate`/`teardown` hooks. That is its whole job. It knows nothing of Docker, the SDLC, issues, or merging, and **never invokes the SDLC engine**.
- **woof** (SDLC engine). Takes a work unit and drives it through the producer/reviewer lifecycle to a merge. It knows nothing of host resources or worktrees - it runs against whatever checkout it is pointed at - and nothing of where work units came from.
- **GTS PM/orchestration** (in this repo). The only layer aware of all three of issues, worktrees, and the SDLC engine. It owns getting external issues local and decomposing them into work units; defining the `provision`/`gate`/`teardown` hooks (the infra stack); and the workflow that composes the two tools.

Three invariants are not negotiable:

1. **The two tools never call each other.** GTS calls both.
2. **worktree never invokes the SDLC engine.** It runs opaque project hooks and stops.
3. **Issue intake and merge/complete are GTS's, never the engine's.** The engine takes a work unit and returns a merge; where the unit came from and how the issue closes are the project's concern.

GTS is a **woof-with-worktrees** project: woof drives the SDLC against a per-worktree containerised stack that the worktree engine provisioned. **VaultForeman is today's transitional stand-in for woof** - "VF drives the worktree" is a today-only detail of that transition, not the target, and GTS never hard-codes VaultForeman.

## Consequences

- GTS keeps no engine code in-repo. The `worktree/` package and `worktree.py` are retired; GTS ships a thin `worktree.toml` (services plus default ports) and the three lifecycle hooks that derive compose project, container names, volumes, subnet, storage, migrations, and env from the injected `WORKTREE_SLOT` and `WORKTREE_PORT_*`.
- Host-resource contention (ports across many projects and worktrees on one host) is solved once, at the host level, by the engine - not re-solved per project.
- The work-unit-to-merge SDLC loop is woof's; GTS does not reimplement dispatch, review, or merge coordination.
- The boundary is durable: this ADR and the vault `docs/runbooks/build-orchestration.md` runbook record it, so the consuming plan (`planning/worktree-engine-consumption.md`) can be deleted once Phase B lands.
