# Job-system contract

Field-level engineering contract for the GTS job system: state machine, timing, transactions,
idempotency, and queue topology. The decisions behind this contract are ADR-0005 (event-state
authority) and ADR-0004 (manifest storage and rerun); the comparison-artefact payload it feeds is
`docs/design/shootout-artefact-contract.md`. This document is declarative: it states what the
system IS once the job-reliability units land. Deviations are bugs.

## Queue topology

Four pgmq queues. Queues are created idempotently at consumer startup; none carry schema.

| Queue | Messages | Producer | Consumer |
|---|---|---|---|
| `shootout_commands` | `start_shootout`, `finalise_shootout` | webapp (outbox), reconciliation | shootout orchestrator (`apps/shootout_orchestrator`) |
| `audio_commands` | `process_audio` | shootout orchestrator (fan-out), retry dispatch | audio worker |
| `source_events` | `sync_gear` | t3k source publisher | t3k-sync worker |
| `dead_letter` | poison-message envelopes | every consumer's max-redelivery path | admin redrive only |

The wiki's six-queue event topology was never built and is not the target. `RenderVideoCommand`
is renamed `StartShootoutCommand` (it starts a shootout; nothing renders video, per ADR-0007) and
gains payload validation equivalent to `ProcessAudioCommand`.

## Job model

`core_jobs` is the unit of work. Columns the contract relies on: `status`, `job_type`,
`parent_job_id`, `entity_id`, `attempt` (starts at 1), `max_attempts` (= 2, see Retry),
`next_retry_at`, `last_heartbeat`, `error`, `completed_at`.

Job types in the shootout pipeline: `SHOOTOUT` (parent), `SHOOTOUT_AUDIO` (per-chain render),
`SHOOTOUT_FINALISE` (new: manifest write + publish gate), `SHOOTOUT_MASTER` (montage enrichment,
demoted to non-gating and dispatched only after finalise). `VIDEO_COMPOSE` is a reserved enum
value with no v1 job (ADR-0007).

## Status state machine

`JobStatus`: PENDING, QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, DEAD_LETTERED.
Terminal set: {COMPLETED, FAILED, CANCELLED, DEAD_LETTERED}.

Allowed transitions and their sole triggers:

| From | To | Trigger |
|---|---|---|
| PENDING | QUEUED | outbox enqueue |
| PENDING, QUEUED | CANCELLED | admin cancel |
| QUEUED | RUNNING | consumer claim |
| RUNNING | RUNNING | re-claim after redelivery, only when `last_heartbeat` is stale |
| RUNNING | COMPLETED | handler success |
| RUNNING | FAILED | handler error; stale-heartbeat reap |
| RUNNING | CANCELLED | admin cancel |
| QUEUED, RUNNING | DEAD_LETTERED | consumer base at max redelivery (`read_ct` > max_retries) |
| FAILED | PENDING | bounded auto-retry (attempt < max_attempts, `next_retry_at` due); admin retry |
| DEAD_LETTERED | PENDING | admin redrive |

COMPLETED and CANCELLED have no exits. A rerun is a new shootout (ADR-0004 G2), never a
transition out of COMPLETED.

Terminal-state meanings are disjoint by construction:

- **FAILED** - the work itself failed (handler exception) or its lease went stale (reap).
  Retryable, automatically once and by admin thereafter.
- **CANCELLED** - explicit admin action. Parent cancel blocks completion only; in-flight
  children finish but are never published (ADR-0005).
- **DEAD_LETTERED** - the message is poison: it exceeded max redelivery. Set by the consumer
  base in the same operation that writes the envelope to the `dead_letter` queue, so the job-row
  state and the queue-level DLQ can never diverge.

## Single-writer transition service

One service is the only writer of `Job.status` and (via projection) `Shootout.status`. No
module may assign either field outside it; a structural guard test enforces this. The service:

1. locks the job row `SELECT ... FOR UPDATE`;
2. validates the move against the transition table (`JobStatus.can_transition_to`); an invalid
   move is a rejected no-op, not an exception path that half-writes;
3. applies bookkeeping (attempt increment on retry claim, `next_retry_at` on retryable failure,
   `error`, `completed_at`, `last_heartbeat` reset);
4. if the job is terminal and part of a shootout tree, reconciles the parent in the same
   transaction (see Reconciliation);
5. commits. The service owns its transaction; callers never commit around it.

Lock order, always: own job row, then parent job row, then shootout row. Concurrent siblings
serialise on the parent row; no writer takes locks in any other order, which makes deadlock
impossible within the job system.

Writers that route through the service: worker success and failure paths, the consumer base's
dead-letter path, the stale-lease reaper, admin cancel, admin retry, admin redrive, and the
scheduled retry sweep. The reaper's raw-SQL terminal write and the master-path's private parent
projection are deleted, not wrapped.

## Enqueue: transactional outbox

One `enqueue_job` service function sends the pgmq message via the session-scoped client and
moves PENDING -> QUEUED in the same transaction, then commits. There is no HTTP enqueue path;
`processing_service.py` and the `worker:8001` call are deleted. Callers: the user-facing
process trigger, the admin enqueue endpoint, both retry paths, and the dispatch sweep - which
becomes a genuine fallback for rows whose outbox transaction was interrupted between job-row
insert and enqueue (possible only for crash-between-requests, since the outbox is atomic).

The admin surface's missing-commit defect is closed by the same move: admin endpoints call
services that own their transactions; no endpoint relies on flush-and-hope.

## Consumer contract

On message receipt the consumer runs the claim algorithm inside one transaction:

1. Lock the job row `FOR UPDATE`.
2. **Terminal guard**: if `status` is terminal, archive the message and return. Redelivered
   messages for finished work are no-ops.
3. If RUNNING and `last_heartbeat` is fresh (< reaper threshold), another consumer holds a live
   lease: release the row and return without acknowledging; the message becomes visible again
   after its timeout. This state indicates a timing bug and is logged loudly.
4. Otherwise claim: QUEUED -> RUNNING (or stale RUNNING -> RUNNING re-claim), set
   `last_heartbeat = now`, commit.

Then the work runs **off the event loop**: the chain executor is synchronous (its `async def`
wrapper was a lie and is removed) and runs via `asyncio.to_thread`, gated by a semaphore of 1 -
one render at a time per worker, event loop free throughout. `/health` answers during renders.

While work is in flight a heartbeat task runs on its own short-lived session every
HEARTBEAT_INTERVAL: it sets `last_heartbeat = now` and extends the message's visibility timeout
(`set_vt`, new method on the `MessageBus` protocol backed by `pgmq.set_vt`) to now +
VT_EXTENSION. The lease is therefore renewed for exactly as long as the render is genuinely
alive; there is no speculative p99 constant.

Completion routes through the transition service (RUNNING -> COMPLETED with the segment write in
the same transaction, see Idempotency); failure routes RUNNING -> FAILED with retry bookkeeping.
Only after the service commits is the message archived.

## Timing constants and invariants

| Constant | Value | Meaning |
|---|---|---|
| HEARTBEAT_INTERVAL | 20 s | lease renewal cadence while work runs |
| VT_INITIAL | 60 s | pgmq visibility timeout at read |
| VT_EXTENSION | 90 s | visibility window granted by each heartbeat |
| REAPER_THRESHOLD | 120 s | `last_heartbeat` age at which a RUNNING job is reaped |
| SWEEP_INTERVAL | 120 s | reaper, retry sweep, and dispatch-fallback loop cadence |
| DISPATCH_CUTOFF | 300 s | age before the fallback sweep re-dispatches a stranded PENDING job |
| max_attempts | 2 | total attempts including the first (one automatic retry) |
| consumer max_retries | 3 | redeliveries before a message is poison (t3k-sync: 5) |
| RETRY_BACKOFF | 120 s | `next_retry_at` offset on retryable failure |

Invariants these values must keep (enforced by a constants test so nobody breaks the ordering
when tuning):

- HEARTBEAT_INTERVAL * 2 < VT_EXTENSION: one missed beat never causes redelivery.
- VT_EXTENSION < REAPER_THRESHOLD: a crashed worker's message redelivers (and can be re-claimed
  by a live consumer) before the reaper declares the job dead; the reaper only ever fires when
  no consumer picked the message back up.
- REAPER_THRESHOLD >= 2 * HEARTBEAT_INTERVAL + VT_EXTENSION is not required; the reaper and
  re-claim race is resolved by the row lock and transition guard, not by timing.

## Retry

A retryable failure sets `next_retry_at = now + RETRY_BACKOFF` when `attempt < max_attempts`,
otherwise leaves the job FAILED with `next_retry_at` NULL for admin action (ADR-0005: bounded to
two attempts total). The retry sweep selects FAILED jobs with `next_retry_at` due, routes
FAILED -> PENDING through the transition service (which increments `attempt` and re-projects the
parent shootout to PROCESSING, permitted because an unpublished generation is not terminal), and
re-enqueues through the outbox. Admin retry is the same path without the attempt cap. The
dormant domain entity methods (`Job.schedule_retry`, `Job.dead_letter` in `gts`) become the
implementation the service calls, replacing direct ORM mutation.

## Reaper

The reaper reaps stale leases, not old jobs: condition is `status = RUNNING AND last_heartbeat <
now - REAPER_THRESHOLD` (SOURCE_SYNC keeps its advisory-lock variant). It routes RUNNING ->
FAILED through the transition service like any other failure, so a reaped render participates in
bounded retry and reconciles its parent. The reaper never touches pgmq: if the reaped job's
message later redelivers, the terminal guard archives it; if the job was re-claimed between the
reaper's read and its lock, the transition guard rejects the stale reap. Raw SQL is gone.

## Reconciliation projection

`Shootout.status` (DRAFT -> PENDING -> PROCESSING -> COMPLETED | FAILED) is a projection of the
job tree, written only by the transition service during reconcile:

- Counting is closed over the whole terminal set. completed = COMPLETED children; failed-class =
  FAILED, CANCELLED, or DEAD_LETTERED children. `total = len(children)`; every terminal child is
  in exactly one bucket. No terminal path can leave the projection unresolved.
- Any failed-class SHOOTOUT_AUDIO child: parent SHOOTOUT job -> FAILED, shootout -> FAILED.
  CANCELLED maps publicly to FAILED; the public lifecycle has five states, never more.
- All children COMPLETED: find-or-create the SHOOTOUT_FINALISE job for `(shootout_id,
  render_version)` and enqueue it through the outbox in the same transaction. This occupies the
  slot the master job holds today; the master-path's direct writes to parent job and shootout
  status are deleted.
- Retry re-projection: a FAILED, unpublished shootout returns to PROCESSING when a child retries.
  A published shootout never re-enters PROCESSING (terminal per generation, ADR-0005/0004).

## Finalise

The SHOOTOUT_FINALISE handler is exactly-once by construction: the find-or-create guard plus the
`core_shootout_manifests` unique key `(shootout_id, version)`. In one transaction it pins this
version's segment per chain, assembles the provenance snapshot, inserts the manifest row, sets
`shootout.status = COMPLETED`, and completes the finalise and parent jobs. Manifest presence is
the public-linking gate (G1): no manifest row, no public link. The montage (SHOOTOUT_MASTER) is
dispatched after finalise as a non-gating enrichment; its failure fails only itself.

## Idempotency keys

| Effect | Key | Mechanism |
|---|---|---|
| segment write | `(shootout_chain_id, version)` | unique constraint + upsert |
| manifest write | `(shootout_id, version)` | unique constraint + find-or-create |
| finalise dispatch | `(shootout_id, render_version)` job | find-or-create under parent row lock |
| message redelivery | job row terminal guard | row lock + archive-and-return |
| enqueue | outbox transaction | send and status flip are atomic |

`AudioSegment.version` and `Shootout.render_version` (the ADR-0004 versioned substrate) land
with the manifest table; media writes are confined to `STORAGE_BASE/<shootout_id>/v<N>/`.

## Enforcement

- A structural guard test fails if any module outside the transition service assigns
  `Job.status` or `Shootout.status`.
- A constants test asserts the timing-invariant ordering.
- Redelivery tests: a redelivered message for a COMPLETED job is a no-op; a redelivered message
  for a stale RUNNING job re-claims; a fresh RUNNING lease is left alone.
- The adversarial migration test covers the pre-fix shapes: duplicate segments for one chain and
  a CANCELLED/DEAD_LETTERED child under a PROCESSING parent must reconcile, not strand.
