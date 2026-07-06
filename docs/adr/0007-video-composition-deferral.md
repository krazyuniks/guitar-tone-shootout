# ADR-0007: Video composition deferral

- Status: accepted
- Date: 2026-07-06
- Depends on: ADR-0003 (shootout comparison artefact model)
- Related: ADR-0003 (indexes this deferral), ADR-0004 (manifest storage and rerun), ADR-0005 (event-state authority), ADR-0006 (public-media security contract)

## Context

Video composition - the Remotion/video-worker pipeline that renders a shootout video - was originally scoped into the shootout lifecycle. Two structural facts from the surrounding artefact set make it wrong to land in v1:

- The durable public artefact is an immutable, versioned manifest written at render completion (ADR-0003, ADR-0004). Video is produced after `SHOOTOUT_FINALISE`, so its URL cannot live inside that immutable snapshot. Video is a post-finalise, read-time enrichment, not a manifest field.
- `VIDEO_COMPOSE` is a new terminal-state writer. The event-state authority (ADR-0005) routes every terminal writer through one reconciliation choke-point; landing a video writer before that choke-point is closed would add a fresh stranding vector to the public projection.

There is also no demand evidence: no usage or share data yet exists to justify the pipeline's build and runtime cost. Fixing the enrichment shape now - without building the pipeline - is what makes video land additively later.

## Decision

Video composition is wholly out of the v1 ship gate.

- No `VIDEO_COMPOSE` job is created in v1. `video.state` reads `absent` by construction, so there is no video stranding surface at all.
- Video does not appear in the immutable manifest payload. Reserving empty keys in an immutable snapshot for an artefact produced after the snapshot is written is incoherent; forward compatibility is carried by `schema_version`, not empty keys.
- Video never gates `shootout.status` = COMPLETED, never appears in the joint public gate (visibility AND COMPLETED AND manifest present), and never becomes a third state authority.

What v1 fixes now, so reopening is purely additive (shape, not execution):

- The public read payload MAY carry an optional projected `video: {url, state}` enrichment object. `state` is a closed in-code enum (`absent | processing | ready | failed`); `url` is opaque-id-based and present only when `state` = `ready`. The Astro island and the app route project it identically. The field-level object shape is delegated to the design doc `design/shootout-artefact-contract.md`.
- Video media is version-scoped storage, keyed to `(shootout_id, render_version)` under `STORAGE_BASE/<shootout_id>/v<N>/`. A `VIDEO_COMPOSE` job may write only inside its own version directory and may never touch a file any existing manifest references.
- A non-gating `VIDEO_COMPOSE` job-tree slot is reserved, dispatched after `SHOOTOUT_FINALISE` as a sibling of the demoted montage, reporting terminal state through the reconciliation choke-point and never counted by the COMPLETED barrier.
- When video lands, its media resolves through the same opaque-id, visibility-plus-lifecycle-checked handler as audio (ADR-0006); the public gate predicate is unchanged.

Explicitly out of the gate: all `VIDEO_COMPOSE` execution and the Remotion/video-worker pipeline; the video-worker internals read-in; video terminal-path hardening; video media serving and any video URL in the public payload; video SEO markup (VideoObject and similar); and any dependency of the montage decision on video (the montage is retained on its own merits, not because video needs it).

Reopen trigger: video composition reopens only when P1 AND P2 AND (D1 OR D2 OR D3).

- P1 - audio A/B live: the first public shootout pages serve from manifests in production with the four blocking gates landed (manifest-before-linking, rerun block/immutability, no terminal path stranding public state in PROCESSING, visibility-gated opaque-id media).
- P2 - event-state substrate closed: the event-state authority (ADR-0005) blocking amendments are landed (reconciliation closed over the full terminal set, master-failure projection, every terminal writer routed through reconciliation, reaper/heartbeat fix). `VIDEO_COMPOSE` must plug into a closed projection, not a holed one.
- D1 - distribution commitment: a product decision to publish GTS content on a video-native channel (YouTube/Shorts, an embed partner) as a growth path.
- D2 - user pull: sustained explicit requests for video export/embed. Placeholder threshold: five distinct requesters within a rolling 30 days.
- D3 - share evidence: share instrumentation shows video-first destinations among the top share targets, or audio-only links measurably underperforming on them.

D2 and D3 thresholds are placeholders, calibrated once traffic exists; the trigger structure does not depend on the numbers. Explicit non-triggers: the video-worker code existing; the montage wanting a consumer; a single anecdotal request; uninstrumented SEO speculation. On firing, the first task is the video-worker/Remotion read-in (does it consume `master.wav` or per-chain segments), which shapes the fast-follow but is not itself a trigger condition.

## Consequences

- The deferral is cheap and stays cheap: an optional read-payload object, an in-code enum, and a directory convention cost nothing at runtime, so there is no sunset pressure on the reservation.
- Video lands additively when the trigger fires: zero migration to the manifest table, zero change to the public gate predicate, zero change to the finalise transaction.
- `Shootout.video_path` survives as a version-scoped enrichment pointer. The free-String `video_status` and `video_job_id` columns stop being authorities and are rationalised in the schema-drift-cleanup pass, independent of when video reopens.
- When video reopens, re-cuts of a published shootout are treated like reruns - blocked while published - unless a versioned video path is added at that point. Whether to backfill existing published shootouts on reopen (dispatching `VIDEO_COMPOSE` against their published `render_version`, which is contract-legal because writing `v<N>/video.*` touches no manifest-referenced file) is a later product and cost call.
- The reopen trigger and its entry contract live in one parked backlog unit; the existing video epics are parked behind that trigger, not closed.
