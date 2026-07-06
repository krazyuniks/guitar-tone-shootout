# ADR-0005: Shootout event-state authority

- Status: accepted
- Date: 2026-07-06
- Related: ADR-0003 (shootout comparison artefact model - this ADR depends on it, and ADR-0003 indexes this contract); ADR-0004 (manifest storage and rerun); ADR-0006 (public media security contract)

## Context

A public shootout page must show one coherent lifecycle state and must never leak private or half-rendered media. Neither guarantee holds structurally today.

Public state is derived ad hoc from the internal job tree. `shootout.status` is a plain String column with no database-level state machine (no PostgreSQL enums), and the value-object transition guards in `JobStatus` are bypassed by direct ORM and raw-SQL writes. There is no visibility concept on a shootout at all - only gear carries `is_public` - so "who may see this shootout" has no home.

`shootout.status` is not an independent state machine; it is a projection of the internal job tree. Its correctness therefore turns on who writes it and when. Several writers reach terminal job state and most bypass reconciliation of the parent shootout: the worker exception paths, the stale-job reaper (`monitor_stale_jobs`), admin `cancel_job`, admin `retry_job`, and the scheduled `process_pending_retries`. Reconciliation itself counts only COMPLETED and FAILED children, so a child that lands in CANCELLED or DEAD_LETTERED fires neither the all-complete nor the any-failed branch, and the shootout strands in PROCESSING.

The stranding is not hypothetical. The reaper dead-letters any non-source-sync RUNNING job whose heartbeat is older than two minutes, and render jobs set their heartbeat once at start, so any render legitimately exceeding two minutes is dead-lettered mid-flight and then never reconciled.

## Decision

A shootout carries exactly two orthogonal public authorities, both columns on `core_shootouts`, and nothing else may derive public state:

- **`shootout.status`** is the sole lifecycle authority: DRAFT -> PENDING -> PROCESSING -> COMPLETED | FAILED. COMPLETED means every per-chain segment has rendered and the manifest has been written - segment completeness plus manifest, never the concatenated montage.
- **`visibility`** (public | unlisted | private, default public) is the sole visibility authority, added by migration and modelled as an in-code value object (no database enum).

The two are independent: visibility is never inferred from lifecycle nor lifecycle from visibility. A FAILED public shootout serves no media; a COMPLETED private one serves media only to its owner.

Everything else is internal orchestration or a subordinate projection, never a third authority:

- `JobStatus` (the seven internal job states) is internal only. The public surface never sees `JobStatus`, job ids, or result paths.
- `video_status` folds into a closed enrichment enum (absent | processing | ready | failed) projected from the video-composition job, surfaced only inside the read payload; it never gates COMPLETED. Video composition is deferred in v1, so no video job runs and this projection reads `absent`.
- `AudioSegment` rows are data, not state; their existence feeds reconciliation and they carry no lifecycle of their own.

**Sole writer.** One reconciliation/transition service is the only writer of shootout terminal state. Workers report their own job terminal state and call reconcile; they never write `shootout.status` directly. Every path that writes a terminal job state routes through this choke-point in the same logical operation and re-projects the parent shootout.

**Closed terminal set.** Reconciliation is closed over the whole job terminal set {COMPLETED, FAILED, CANCELLED, DEAD_LETTERED}. Any SHOOTOUT_AUDIO child reaching FAILED, CANCELLED, or DEAD_LETTERED projects the shootout to FAILED and terminates the parent SHOOTOUT job. CANCELLED maps publicly to FAILED; the public lifecycle does not grow a sixth state. No terminal job path may leave `shootout.status` stranded in PROCESSING.

**Reaper does not kill live renders.** The stale-job reaper must not dead-letter a render that legitimately exceeds its heartbeat threshold: render job types either heartbeat periodically while rendering or are excluded from / raised above the two-minute threshold. This is a standing correctness bug independent of the projection.

**Joint public gate, defence in depth.** Every public surface additionally filters visibility permits access AND `status = COMPLETED` AND manifest present, enforced independently at each read surface - the listing, browse, and read-payload queries and the media handler - so a stranded or corrupted projection degrades to invisibility, never to leakage or a broken page. Unlisted is excluded from listings and sitemaps but reachable by direct id; private requires owner auth. This ADR owns the joint predicate on the shootout query surfaces; the per-request media-handler enforcement is owned by ADR-0006.

**Owner-settled behaviours:**

- **Parent cancel blocks completion only.** Cancelling a parent SHOOTOUT does not plumb cancellation into in-flight children in v1: children finish but are never published, and the projection reaches FAILED. There is no child-cancellation cascade in v1.
- **Bounded auto-retry.** The timer-driven auto-retry stays, bounded to two attempts total (one retry). After the cap the render stays FAILED for admin action. Both retry writers - admin `retry_job` and the scheduled `process_pending_retries` - route their FAILED -> PENDING transition through the reconciliation choke-point and re-project the parent per the terminal-per-generation rule.

Terminal is terminal per render generation: a published shootout never re-enters PROCESSING while its published media remains the live artefact. Rerun generation handling is ADR-0004's.

## Consequences

- `core_shootouts` gains a `visibility` column; a migration and an in-code value object land with it. Every public listing, browse, and read-payload query applies the joint predicate, not visibility alone.
- The reconciliation service becomes the single terminal-state writer. The worker exception paths gain a catch-all that lands the job in a terminal state before the message is dead-lettered; the reaper, admin cancel, admin retry, and the scheduled retry sweep all route through it.
- Reconciliation counting closes over CANCELLED and DEAD_LETTERED, and the master/finalise path can no longer strand PROCESSING.
- Render jobs heartbeat during rendering (or are exempt from the reaper threshold), so long renders are no longer dead-lettered mid-flight.
- The public surface is safe by construction even against a projection bug: the joint gate makes a stranded shootout invisible rather than leaky.
- Field-level schemas - the column definitions, value-object shapes, reconciliation transition table, and read-payload projection - are specified in the GTS artefact-contract design doc (`design/shootout-artefact-contract.md`); this ADR records the decision, not the schema.
