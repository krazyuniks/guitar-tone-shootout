# Jobs Wiki Consolidation Plan

## Goal

Create one authoritative wiki page for all job-system architecture and operations, while keeping audio/video implementation internals in their existing pages.

This central page becomes the source of truth for:

- Job architecture rationale and bounded-context boundaries
- Infrastructure/process model (worker, scheduler, container runtime)
- TaskIQ vs pgmq roles
- Producer/consumer flow and dispatch boundaries
- Outer loop / inner loop timing model (tick, batch, heartbeat, lock)
- Scheduled job catalog and per-job high-level behavior
- Operational observability and runbook entry points

Lower-level implementation details remain in `docs/plans/` and code docs.

---

## Proposed Canonical Page

Create:

- `../wiki/Jobs-Architecture-and-Operations.md`

Keep:

- `../wiki/GTS-Technical-Architecture.md` as system-wide architecture index
- `../wiki/REFERENCE-ARCHITECTURE.md` as implementation-agnostic reference
- `../wiki/Audio-Processing.md` and `../wiki/GTS-Remotion-Architecture.md` for processing internals only
- `../wiki/IMPLEMENTATION.md` for phase tracking/status only

---

## Canonical Page Outline

1. Scope and non-goals
2. Bounded-context ownership and dependency rules
3. Runtime topology (containers, processes, profiles)
4. Control planes and data planes
   - TaskIQ control plane
   - pgmq data plane
5. End-to-end job flows
   - User-triggered processing flow
   - Source sync flow (scheduler -> SOURCE_SYNC -> pgmq consumer -> core)
6. Scheduler model
   - Tick cadence, lock TTL, heartbeat, non-overlap guarantees
7. SOURCE_SYNC loop model
   - Outer dispatch cadence
   - Inner batch pass semantics
   - Yield/requeue behavior
8. Job catalog (table)
   - Trigger, owner, idempotency, retry semantics, observability keys
9. Dispatch boundary and decoupling
   - Current state
   - Target state (align with `docs/plans/2026-02-19-core-job-dispatch-decoupling.md`)
10. Operations
   - Admin API/CLI surfaces
   - Health checks, lag checks, queue depth, stale-job detection
11. Failure modes and recovery
12. Change policy
   - What belongs here vs implementation docs

---

## Content Move Map

### 1) `../wiki/GTS-Technical-Architecture.md` -> Move to canonical jobs page

Move these job-focused sections (or equivalents):

- Message queue (pgmq) architecture and consumer pattern
- Job Scheduling (TaskIQ)
- Source sync flow diagram
- Job lifecycle, retry, heartbeats, locks
- Worker/scheduler container roles
- Admin API architecture for jobs/sync operations
- Jobs profile/runtime topology

Then replace those sections in `GTS-Technical-Architecture.md` with concise summaries and links to the new page.

### 2) `../wiki/IMPLEMENTATION.md` -> Keep only delivery status; remove architecture duplication

Keep:

- Phase status, dependencies, checklist progress

Replace duplicated architecture detail in phases 5A/5D/5E with:

- Short status notes
- Link to canonical jobs page for architecture and runtime behavior
- Link to `docs/plans/` for implementation plans

### 3) `../wiki/REFERENCE-ARCHITECTURE.md` -> Keep principles only

Keep:

- Source-agnostic principles (transactional send, outbox migration path, idempotency)

Avoid runtime-specific details (container/process specifics) that should live only in canonical jobs page.

### 4) `../wiki/Audio-Processing.md` -> Remove orchestration duplication

Keep:

- DSP pipeline, model loading, loudness, chain execution internals

Remove/replace:

- Job hierarchy/orchestration references -> link to canonical jobs page.

### 5) `../wiki/GTS-Remotion-Architecture.md` -> Keep video BC integration internals

Keep:

- Video BC ownership and render API contract

Replace:

- Task orchestration ownership details (worker/job hierarchy) with a short link to canonical jobs page.

---

## Consistency Corrections Required During Consolidation

1. Admin endpoint prefix consistency:
   - Align all docs on canonical admin route prefix (`/api/admin/*` vs `/admin/*` mismatch currently documented).
2. Dispatch boundary clarity:
   - Document current coupling and target decoupled path from `docs/plans/2026-02-19-core-job-dispatch-decoupling.md`.
3. Process model clarity:
   - Explicitly document which process starts what in worker/scheduler runtime and how multiple processes are supervised.
4. Scheduler cadence:
   - Document intended tick granularity and why (e.g., 10s vs 60s tradeoff).

---

## Editing Sequence (Low-Risk)

1. Draft `Jobs-Architecture-and-Operations.md` with diagrams and glossary.
2. Update `GTS-Technical-Architecture.md`:
   - Keep short "Jobs Overview" summary
   - Link to canonical page for details
3. Update `IMPLEMENTATION.md`:
   - Trim architecture duplication in phase sections
   - Keep only progress/status/checklists
4. Update `Audio-Processing.md` and `GTS-Remotion-Architecture.md`:
   - Remove orchestration duplication
   - Link to canonical page
5. Run final doc pass for terminology consistency:
   - `SOURCE_SYNC`, `gear_sync`, `TaskIQ`, `pgmq`, `worker`, `scheduler`, `jobs profile`

---

## Definition of Done

- Exactly one wiki page is authoritative for job architecture/operations.
- Other wiki pages reference it instead of repeating runtime details.
- Audio/video pages contain only processing internals and explicit integration links.
- Implementation plan docs in `docs/plans/` hold lower-level and evolving details.
- No contradictory statements remain for:
  - endpoint prefixes
  - dispatch boundaries
  - runtime process model
  - scheduler cadence/heartbeat semantics
