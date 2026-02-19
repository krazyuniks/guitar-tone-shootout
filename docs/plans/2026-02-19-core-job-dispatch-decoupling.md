# Core Job Dispatch Decoupling Plan

## Summary

The current job dispatch path couples `webapp` (user-facing bounded context) to the worker control plane via direct HTTP calls to the worker admin API. This is an architecture leak. The recommended fix is to make `gts_core` the asynchronous handoff boundary using a transactional queue/outbox pattern, then let worker-side consumers dispatch TaskIQ.

This keeps `webapp` responsible for domain intent ("a job should run") while worker/infrastructure own execution transport details.

---

## Problem Statement

Current flow:

1. Web request hits `webapp` user API.
2. `webapp` writes a row in `gts_core.jobs`.
3. `webapp` directly calls worker admin API `/api/admin/enqueue`.
4. Worker admin dispatches TaskIQ.

Why this is a problem:

- `webapp` has infrastructure knowledge (worker URL, control endpoint).
- User request path depends on worker admin API availability.
- Cross-context dispatch is imperative RPC, not durable event handoff.
- Retry and replay semantics are split across HTTP failures and DB state reconciliation.
- It conflicts with the source sync style, where transactional queueing is already used.

---

## Architectural Gap

### Expected Boundary

- `webapp` should write domain state and intent in `gts_core`.
- Worker-side components should consume intent and perform execution dispatch.
- Infrastructure transport should be internal to async infrastructure, not a web request concern.

### Actual Boundary

- `webapp` calls worker admin API directly for dispatch.
- Worker admin API is acting as both operator plane and domain dispatch plane.

---

## Proposed Solution

Implement a `gts_core` job-intent queue (pgmq) or outbox, produced transactionally with job writes, consumed by worker.

### Recommended Target Pattern

1. In a single DB transaction in `gts_core`:
   - Insert/update `jobs` row.
   - Publish `job_dispatch_intent` message (or write outbox row).
2. Worker `job-intent-consumer` reads intents.
3. Consumer dispatches TaskIQ `.kiq(job_id)` by `job_type`.
4. Consumer updates `jobs.task_id` + `status=queued` idempotently.
5. Consumer archives success or routes to DLQ/retry path.

This mirrors the source pipeline design principle: transactional send + async consumer.

---

## Message Contract (Minimal)

Queue/topic: `job_dispatch_intent` (in `gts_core`)

Payload:

- `job_id` (UUID, required)
- `job_type` (string enum, optional but recommended)
- `created_at` (timestamp, optional for observability)
- `dispatch_version` (int, optional, default 1)

Idempotency key:

- `job_id` alone is sufficient if consumer checks existing `task_id`/status before dispatch.

Consumer rules:

- If `task_id` already set or status not dispatchable, no-op + archive.
- If job missing, send to DLQ with reason.
- If dispatch fails transiently, retry with backoff.
- If retries exhausted, DLQ and keep job in failed-dispatch state.

---

## Phased Migration Plan

### Phase 1: Introduce Intent Queue (No Behavior Change)

- Add `gts_core` pgmq queue: `job_dispatch_intent` + `job_dispatch_intent_dlq`.
- Add worker consumer process/module for this queue.
- Keep existing HTTP enqueue path active.
- Add idempotent consumer logic so duplicate dispatch attempts are safe.

Exit criteria:

- Consumer runs and processes synthetic test intents correctly.

### Phase 2: Dual-Write from Webapp

- In webapp job-creation transaction, write `jobs` + enqueue `job_dispatch_intent`.
- Keep existing HTTP enqueue call temporarily (dual path).
- Use idempotency in worker to avoid duplicate execution.

Exit criteria:

- All jobs still dispatch correctly with no regressions.

### Phase 3: Remove Webapp -> Worker Admin Dispatch

- Remove direct `enqueue_to_worker` calls from user request paths.
- Webapp only writes job + intent.
- Keep admin enqueue endpoint for manual/operator use only.

Exit criteria:

- Production job dispatch does not rely on worker admin API calls from webapp.

### Phase 4: Simplify Recovery Paths

- Reevaluate scheduler `dispatch_pending_jobs` recovery task.
- Keep as safety fallback or remove if redundant with queue semantics and DLQ tooling.
- Finalize runbooks and alerts for intent queue depth and DLQ.

Exit criteria:

- Operational runbooks and alerts cover dispatch queue health.

---

## Operational Considerations

### Observability

Track at minimum:

- Intent queue depth
- Dispatch success/failure counts
- Time from intent creation to TaskIQ queueing
- DLQ count + top error reasons

### Failure Modes

- Worker down: intents accumulate durably in DB queue.
- Redis down: consumer retries dispatch and does not drop intents.
- Duplicate intent: idempotent no-op.
- Poison message: DLQ + alert.

### Backward Compatibility

- Keep worker admin enqueue endpoint for operator actions and scripts.
- Restrict use to control-plane operations, not normal webapp request path.

---

## Benefits

- Restores bounded-context separation.
- Removes worker API dependency from user request path.
- Gives transactional durability for dispatch intents.
- Standardizes async architecture with existing source ingestion model.
- Improves replay/recovery and simplifies future multi-source expansion patterns.

---

## Risks and Mitigations

- Risk: duplicate dispatch during migration.
  - Mitigation: idempotent worker dispatch checks by `job_id`/`task_id`.

- Risk: more moving parts (new consumer/queue).
  - Mitigation: phased rollout, queue metrics, DLQ runbook.

- Risk: hidden dependencies in current retry/recovery logic.
  - Mitigation: keep existing recovery task until new path proves stable.

---

## Action Checklist

1. Add `job_dispatch_intent` queues in `gts_core`.
2. Implement worker intent consumer with idempotent dispatch.
3. Add enqueue helper in webapp persistence path (transactional).
4. Dual-write and validate metrics.
5. Remove direct webapp worker-admin enqueue calls.
6. Update runbooks/alerts and finalize cleanup.
