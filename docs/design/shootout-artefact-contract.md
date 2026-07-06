
# Shootout artefact contract - consolidated design and implementation spec

This is the single home for the field-level schemas, column shapes, and code-path detail that the
GTS shootout ADRs delegate to a design doc. Each ADR records its decision, context, and consequences
and points here for the detail:

- ADR-0003 shootout-comparison-artefact-model -> section 1
- ADR-0004 shootout-manifest-storage-and-rerun -> section 2
- ADR-0005 shootout-event-state-authority -> section 3
- ADR-0006 public-media-security-contract -> section 4
- ADR-0007 video-composition-deferral -> section 5

(ADR-0001 is the Vite + React SPA app surface; ADR-0002 is the worktree-engine consumption boundary.
Neither is a shootout-contract ADR.)

## Terminology

- **Signal chain** - one amp/cab/pedal/NAM-profile configuration played over the shared DI.
- **Shootout** - an A/B comparison of several signal chains over one shared DI.
- **AudioSegment** - the rendered audio for one chain in one render generation. Per-chain segments are
  the comparison substrate the player consumes.
- **Manifest** - the immutable, versioned snapshot written at render completion (per-chain media,
  waveform, LUFS/peak, gear provenance). The durable public artefact.
- **Montage** (`master.wav`) - the concatenated sequential mix. A non-gating enrichment for
  share/download/SEO preview; the player never consumes it.
- **Visibility** - a column on `core_shootouts` separate from lifecycle `status`; `published` means
  publicly linkable.
- **render_version** - the monotonic generation counter for a shootout's renders.

## Ship gates

Four blocking gates recur across the sections; the sections below give their mechanics:

- **G1** manifest-before-public-linking - no public page or embed renders from live joins (section 2, 4).
- **G2** rerun immutability for published artefacts - a rerun never mutates or deletes media a published
  manifest references (section 2).
- **G3** no terminal job path may strand `shootout.status` in PROCESSING (section 3).
- **G4** visibility column plus visibility-gated media serving (section 3, 4).

Repo paths below are relative to the GTS delivery repo. Line references are anchors to current code the
work amends, not durable coordinates.

---

## 1. Artefact model (ADR-0003)

**Substrate.** Per-chain `AudioSegment`s are the A/B comparison substrate. Every chain is rendered over
the same DI from t=0, so the segments are start-aligned by construction and the player plays them
time-aligned. The player reads segments; it never reads the montage.

**Montage demoted.** The concatenated `master.wav` is a non-gating montage/share/download/SEO-preview
enrichment. It is retained (already built, near-zero marginal cost, probable future video input) but is
no longer the comparison object. `Shootout.output_path` never reaches a player payload.

**Durable artefact.** The durable public artefact is a first-class, immutable, versioned manifest
written at render completion, carrying a render-time provenance snapshot. It is the only substrate any
public surface reads from.

**Derived-on-read is rejected (CASCADE).** A public page cannot live-join the source rows because
`core_shootout_chains.signal_chain_id` is `ondelete=CASCADE`: deleting or replacing a source signal
chain cascades `SignalChain` -> `ShootoutChain` -> `AudioSegment`, destroying the rows a live-joined
public page depends on. The snapshot manifest is immune to this because it holds no foreign keys into
those rows (section 2). Live rows remain for the owner's edit/rerun view; the public artefact reads
only the snapshot.

**Timeline and alignment.** Start-aligned by construction. The manifest carries per-chain
`duration_seconds` and `waveform`; the shootout timeline duration is the max per-chain duration (effect
and IR tails may differ across chains). No per-chain offset/latency metadata in v1 (deferred; the
trigger is measured audible start-skew between chains).

**Gear provenance.** Snapshotted per chain at render time, never live-joined. Each chain carries an
ordered block list; each block records the stage/gear type, display name, platform (NAM / IR / ...),
an icon/image ref by stable asset id, and the parameter settings used for that render.

**OutputMatrix cap = 16 chains.** A shootout compares at most 16 signal chains. The matrix is
combinatorial (2 amps x 2 cabs x 2 pedals = 8, and up), so the cap sizes three things without changing
the contract shape:

- **Render fan-out** - up to 16 SHOOTOUT_AUDIO render jobs per shootout; sizes render concurrency and
  time-per-shootout.
- **Manifest size** - up to a 16-entry ordered `chains` array, each entry carrying a waveform; sizes the
  manifest payload budget.
- **Player UX** - the comparison player must stay usable at 16 tones (A/B/C reads cleanly; sixteen is
  the design ceiling the player must accommodate).

The cap is a design input, not a blocker.

---

## 2. Manifest storage, finalise, and rerun (ADR-0004)

### 2.1 Storage: `core_shootout_manifests`

An insert-only side table, not a JSON column on `core_shootouts` (a single column would force
overwrite-to-version, re-admitting the public-artefact mutation G2 forbids, and would bloat every
shootout list-row with waveform-sized payloads).

| column | type | notes |
|---|---|---|
| `id` | UUIDv7 | primary key |
| `shootout_id` | FK -> `core_shootouts.id`, `ondelete=CASCADE` | the only delete path is the owner deleting the whole shootout (intentional unpublish-by-delete) |
| `version` | int | equals the `render_version` of the successful run; failed runs leave gaps, which is fine - monotonicity is all that is required |
| `schema_version` | int | manifest schema generation; forward compatibility is carried here, not by empty reserved keys |
| `payload` | JSONB | the full snapshot (schema below) |
| `created_at` | timestamp | |

Unique constraint on `(shootout_id, version)`. Insert-only: no UPDATE and no targeted-DELETE path
exists in application code. The payload holds **no foreign keys** into chains, segments, signal chains,
or gear - that absence is what makes it immune to the signal-chain CASCADE.

Rejected alternatives: a JSON column on `core_shootouts`; a filesystem `manifest.json` beside the media
(no transactional publish with the status flip, no SQL-queryable "manifest present" gate, and it would
re-introduce a second path-identified artefact when the whole contract exists to launder paths into
opaque ids).

### 2.2 Supporting columns

- `Shootout.render_version` (int, default 0) - a monotonic counter, incremented in the same transaction
  that creates the parent SHOOTOUT job (the run-request transaction).
- `AudioSegment.version` (int) with a unique constraint on `(shootout_chain_id, version)` - deterministic
  segment identity, replacing the current unordered `segments[0]` pick that is nondeterministic after any
  rerun.

### 2.3 Manifest JSON payload schema (schema_version 1)

The stored payload is the full internal snapshot. Internal-only fields (storage-relative paths, pinned
segment ids) are present in storage and stripped at wire-payload assembly (the wire projection is
section 4's allow-list).

- `schema_version`: 1
- `shootout`: id, title, description, creator attribution, created date
- `di`: DI descriptors - name, guitar, pickup, tuning, duration
- `timeline`: `{ aligned: "start", duration_seconds: <max chain duration> }`
- `chains`: ordered array (max 16), each entry:
  - `label`
  - `media_path` (storage-relative, server-internal, e.g. `v3/<chain_id>.wav`) - never emitted on the wire
  - `segment_id` (the pinned `AudioSegment` id for this version) - never emitted on the wire
  - `duration_seconds`
  - `waveform`
  - `integrated_lufs`
  - `peak_dbfs`
  - `provenance`: ordered block list; each block `{ stage / gear_type, display_name, platform, icon_asset_id, parameters }`

Montage and video URLs are **not** in the manifest payload - they complete after finalise and live in
the read-payload enrichment section (sections 4 and 5). Loudness note: segments are already normalised
to -14 LUFS, so `integrated_lufs`/`peak_dbfs` are display metadata; no gain-matching UI is required in v1.

### 2.4 Media resolution goes through the manifest

Public media resolves opaque URL -> manifest row -> version-scoped storage-relative path -> file, gated
on the joint predicate (section 4). Resolution never goes through `AudioSegment` rows: if it did, a
signal-chain delete would cascade the rows away and 404 published media even though the files still exist
on disk. The relative paths in the payload are server-internal; the wire exposes only opaque id-based
URLs. No change to the existing CASCADE is required for v1.

### 2.5 `SHOOTOUT_FINALISE` job

Finalisation is the single step that makes state public, so it is a Job (retryable, observable), not
inline logic in `reconcile_parent_after_audio` (inline assembly at the all-children-complete barrier has
no retry driver if it fails after the last child commits COMPLETED - the shootout would strand in
PROCESSING with no driver).

- `SHOOTOUT_FINALISE` is a new JobType (in-code value object, no DB enum, consistent with house style).
- `reconcile_parent_after_audio` find-or-creates it when all SHOOTOUT_AUDIO children are COMPLETED -
  exactly the slot where it find-or-creates `SHOOTOUT_MASTER` today (`shootout_reconciliation.py`
  ~90-108). Dispatched on `audio_commands`, handled by the audio-worker `process_audio_job` switch. No
  queue topology change.
- Handler, in one transaction: pin this version's segment per chain; assemble the payload (provenance
  snapshot via joins at that moment); insert the manifest row; set `shootout.status` = COMPLETED;
  complete the finalise job and the parent SHOOTOUT job. The find-or-create guard plus the
  `(shootout_id, version)` uniqueness constraint make it exactly-once.
- After commit, the handler find-or-creates and dispatches `SHOOTOUT_MASTER` as a non-gating enrichment
  child. Sequencing finalise before montage structurally closes the master-strand hole: once
  `shootout.status` is COMPLETED, a montage failure can only fail the montage job.
- `Shootout.output_path` / `Shootout.video_path` remain as version-scoped enrichment pointers
  (e.g. `v<N>/master.wav`), surfaced in the read payload as `{url, state}`, stable while the rerun block
  holds.

### 2.6 Rerun semantics

v1 rule (owner decision): **every run creates a NEW shootout.** There is no in-place edit-and-rerun in
v1. The versioned substrate and the published-rerun guard are protection and future-proofing, not an
exposed v1 UX.

- **Block-while-published.** A rerun is blocked while published. `published` = a manifest exists AND
  `status` = COMPLETED AND `visibility` in `{public, unlisted}`. Until the visibility column lands, the
  interim predicate is `manifest exists AND status = COMPLETED` (the product is public-by-default, so
  every completed shootout must be treated as potentially linked). Enforced at the webapp run-request
  handler (reject enqueue of the parent SHOOTOUT job); the `(shootout_id, version)` uniqueness constraint
  is defence in depth at the finaliser.
- **Version-scoped writes.** An unpublished rerun allocates `render_version` + 1 in the run-request
  transaction, stamps it into the parent job payload, and children carry it. All media renders into
  `STORAGE_BASE/<shootout_id>/v<version>/`. A render job may only ever write inside its own version
  directory and never touches a file referenced by any existing manifest - this is what satisfies G2.
- **Row accumulation.** A SHOOTOUT_AUDIO job replaces its own `(chain, version)` segment row on retry
  (safe: that version has no manifest yet). Cross-version rows are intentional and bounded; the manifest
  pins exact segment ids and paths, and the montage consumes the pinned set, never `segments[0]`.
- **Retention.** Superseded/failed version directories and rows are retained in v1; GC/retention tooling
  is deferred.

Lifting the block later (atomic versioned republish) needs only removing the guard and adding an atomic
latest-version flip - no schema migration. That is why blocked-with-versioned-substrate beats
blocked-with-overwrite.

---

## 3. Event-state authority and terminal rules (ADR-0005)

### 3.1 Two orthogonal authorities

Exactly two authorities, both columns on the `core_shootouts` row, orthogonal and never inferred from
each other:

- `shootout.status` - the sole public lifecycle authority.
- `visibility` (public | unlisted | private) - the sole visibility authority. It exists nowhere today
  (only gear has `is_public`); added by migration as an in-code value object (no DB enum), default
  public.

Orthogonality: a FAILED public shootout serves no media; a COMPLETED private one serves media only to
its owner. Everything else - `JobStatus`, `AudioSegment` rows, `video_status`, queue/DLQ message state -
is internal orchestration or a subordinate projection. No surface may derive public state from anything
but these two columns.

### 3.2 Lifecycle and subordinate projections

- `shootout.status`: DRAFT -> PENDING -> PROCESSING -> COMPLETED | FAILED (five states). COMPLETED means
  all per-chain segments rendered and the manifest written - segment completeness plus manifest, never
  the montage.
- `JobStatus` (7 states) is internal orchestration only. The owner's app may poll jobs for progress; the
  public surface never sees `JobStatus`, job ids, or `result_path`. Job progress stays on the existing
  jobs polling API; the manifest is not a progress channel.
- `video_status` folds into a closed in-code enum projection of the VIDEO_COMPOSE job
  (absent | processing | ready | failed), surfaced only inside the read payload. Never a third authority,
  never gates COMPLETED (section 5).
- `AudioSegment` rows are data, not state; their existence feeds reconciliation but they carry no
  lifecycle of their own.

### 3.3 Single reconciliation choke-point

`shootout.status` is a projection of the internal job tree, not an independent state machine. The
central invariant is therefore about writers: every terminal transition of any job in a shootout's tree
must trigger reconciliation of the projection. The database enforces no state machine (plain String
columns, no PostgreSQL enums) and the value-object transition guards are bypassed by direct ORM and
raw-SQL writes, so the only viable enforcement is a **single choke-point**: one transition/reconciliation
service that is the sole writer of shootout terminal state. Every other component is reduced to a reader
or a caller. Workers report their own job terminal state and call reconcile; they do not write
`shootout.status` directly.

### 3.4 Terminal-state rules

1. The job terminal set is `{COMPLETED, FAILED, CANCELLED, DEAD_LETTERED}` (as `job_status.py`
   declares). Reconciliation must be closed over the whole set; today `reconcile_parent_after_audio`
   (~lines 67-68) counts only COMPLETED and FAILED.
2. Any SHOOTOUT_AUDIO child reaching FAILED, CANCELLED, or DEAD_LETTERED projects shootout -> FAILED and
   the parent SHOOTOUT job -> terminal. CANCELLED maps publicly to FAILED - the 5-state lifecycle does
   not grow a sixth state.
3. All children COMPLETED plus manifest written projects shootout -> COMPLETED. v1 fallback if completion
   stays inside the master job: a master failure must set shootout FAILED and terminate the parent
   (today `consumer.py` ~335-345 fails only the master job row). The end-state (section 2's finalise plus
   montage demotion) removes the master from the completion path entirely.
4. Every writer of a terminal job state triggers reconciliation in the same logical operation. Today
   four writer paths exist and three bypass reconciliation, plus a scheduled retry writer:
   - worker catch blocks - reconcile only for the three caught exception types; any other exception
     leaves the job RUNNING while the consumer retries/DLQs the message. Needs a catch-all landing the
     job in a terminal state before the message is DLQ'd.
   - `monitor_stale_jobs` (`t3k_sync/tasks.py`) - raw SQL UPDATE to DEAD_LETTERED with no reconcile.
     Must collect affected shootout-tree job ids and reconcile each (or write through the choke-point).
   - admin `cancel_job` - sets CANCELLED with no reconcile and no child cascade. Must reconcile.
   - admin `retry_job` (`api/admin.py` ~193) - resets to PENDING, clears error, flushes; it never
     reconciles or re-projects the parent. Must route through the choke-point and re-project the parent
     out of FAILED.
   - `process_pending_retries` (`t3k_sync/tasks.py` ~281-300) - a scheduled raw
     `UPDATE core_jobs SET status = PENDING WHERE status = FAILED AND next_retry_at <= now AND attempt <
     max_attempts`, bypassing the choke-point exactly like admin retry. Routes through the same path.
   (Dispatch itself is already handled for the retry paths by the scheduled `dispatch_pending_jobs`; the
   missing guarantee is transition/reconciliation, not dispatch.)
5. Terminal is terminal per render generation. A rerun (section 2's G2) moves the projection atomically
   to a new generation; a published shootout never re-enters PROCESSING while its published media remains
   the live artefact.
6. Defence in depth regardless of projection correctness: all public queries additionally filter
   `status = COMPLETED AND manifest present`, so a stranded or corrupted projection degrades to
   invisibility, never to leakage or a broken public page.

### 3.5 Closed terminal set - no PROCESSING stranding

Three live mechanisms strand PROCESSING today; closing the terminal set (rules 1-4) plus the reaper fix
removes all three:

1. `monitor_stale_jobs` dead-letters any non-source-sync RUNNING job whose heartbeat is older than 2
   minutes via raw SQL with no reconciliation - and SHOOTOUT_AUDIO/SHOOTOUT_MASTER jobs set
   `last_heartbeat` exactly once at start, so any render exceeding 2 minutes is dead-lettered mid-flight.
2. `reconcile_parent_after_audio` counts only COMPLETED and FAILED, so a DEAD_LETTERED or CANCELLED child
   fires neither the all-complete nor the any-failed branch.
3. The master-failure path sets only its own job FAILED, leaving the shootout PROCESSING and the parent
   RUNNING.

Mechanisms 1 and 2 compose: a long render is reaped, the child sits DEAD_LETTERED, the shootout sits
PROCESSING forever.

### 3.6 Reaper-versus-render race resolution

Fix the 2-minute reaper killing legitimate long renders: heartbeat periodically during rendering, or
exclude/raise the threshold for render job types. This is independent of the projection - it is a
standing production hazard and can land first.

### 3.7 Parent cancel - block reconcile only

When a parent SHOOTOUT job is cancelled while child renders are in flight, v1 **blocks reconcile
completion only**. In-flight children finish but are never published; the public projection reaches
FAILED. There is no cancellation plumbing in v1 (no signal-cancel of running audio jobs). The wasted
render is bounded and invisible.

### 3.8 Auto-retry - kept, bounded to 2 attempts

The timer-driven auto-retry (`process_pending_retries`) is kept, bounded to **2 attempts total (one
retry)**. A second failure signals a deeper problem, not a transient blip, so retrying stops and the
render stays FAILED for admin attention. The retry counter/cap lives on the render/job row; the timer
skips rows at the cap. Every retry writer (admin `retry_job` and `process_pending_retries`) routes
through the single reconciliation choke-point, and the projection still reaches FAILED via that
choke-point.

---

## 4. Public media security and read-payload allow-list (ADR-0006)

The starting position is favourable: no public media path exists today - both streaming endpoints
(`/audio/master`, `/chains/{id}/audio`) are owner-only and 404 everyone else. The contract is
build-correct-from-day-one, with one remediation item (the `file_path` already exposed in the DITrack
response schema).

### 4.1 The joint public gate

A single predicate, evaluated per request at every read surface independently (defence in depth, so a
bug at one surface degrades to a 404, never to leakage):

`(visibility = public, or visibility = unlisted when addressed by direct id) AND status = COMPLETED AND a manifest row exists`

Enforcement surfaces, each independent, none relying on another having checked:

1. SQL visibility filters on every public listing/browse query (unlisted is excluded from all listings,
   browse queries, sitemaps, and feeds).
2. The shootout read-payload endpoint.
3. The media handler, per request, for every media type it serves.

Private requires owner auth under the existing SEC-query-ownership discipline.

### 4.2 Opaque, manifest-only media resolution

Media identity on the wire is opaque ids only. URLs encode no filesystem information - no paths, no
storage layout, no version-directory structure, no extensions derived from `file_path`. The resolution
chain is `opaque id -> manifest row -> version-scoped storage-relative path -> STORAGE_BASE containment
check -> stream`. The handler never accepts client-supplied path input of any kind.

Resolution splits by media type, gating uniform across all of them:

- **Per-chain segment media** resolves through the manifest-pinned segment entries (section 2.3).
- **Montage and video media** resolve by opaque id to the version-scoped enrichment pointers bound to
  the published render version - never live `Shootout.output_path` / `Shootout.video_path`.

The HMAC-signed `/api/files/{signature}` route is not reused, relaxed, or extended for the public
surface: expiring signatures cannot be baked into static Astro pages, and non-expiring ones would be
permanent bearer capabilities that survive a visibility change. The existing owner-only streaming
endpoints stay owner-only; the public handler is new and additive.

### 4.3 Four media-handler guarantees (all contract)

1. **Per-request gating** - the joint predicate is evaluated on every media request (segments, montage,
   video, any future media enrichment), so a page bug can never become a media leak and a media bug can
   never resurrect a page.
2. **Manifest-only resolution** - public serving never reads `AudioSegment.file_path`,
   `Shootout.output_path`, or `Shootout.video_path` live; it reads what the published manifest (and, for
   montage/video, the version-scoped enrichment pointers) pins.
3. **Published-media immutability** - files referenced by any existing manifest are never overwritten or
   deleted, guaranteed by version-scoped write discipline plus block-rerun-while-published, plus the rule
   that no row cascade ever triggers file deletion.
4. **Uniform not-found semantics** - private, non-existent, not-COMPLETED, and manifest-absent all return
   the same 404 at both page and media handler. The existence of private shootouts is never disclosed
   via status-code or timing-differentiated responses.

### 4.4 Wire read-payload allow-list

The public payload is an allow-list, not a redaction of internal rows. One shape serves both the Astro
island and the app route; owner-only data (job progress, edit affordances) stays on the authenticated
endpoints and is never merged in. The wire payload is a projection of the manifest with internal fields
stripped; the raw manifest JSONB is never returned by any endpoint.

Permitted fields:

- `id`, `title`, `description`
- creator attribution: `username`, `avatar` (never raw `user_id`, never email)
- `created` date
- DI descriptors: `name`, `guitar`, `pickup`, `tuning`, `duration`
- ordered `chains`, each `{ label, media_url (opaque id-based), duration_seconds, waveform,
  integrated_lufs, peak_dbfs, provenance }` where `provenance` is the block list with gear display names,
  platform, and icon refs by stable asset id
- `timeline`: start-aligned, `duration = max chain duration`
- optional `montage_url`
- optional `video: {url, state}` (section 5)
- optional `comment_count`

Absolute exclusions, in **all** payloads (public and app alike), and `file_path` is one of them:

- `file_path`, `output_path`, `result_path`, `video_path`, and any storage-relative path
- `JobStatus`, job ids, `video_job_id`, `task_id`, `error`, attempt/retry fields
- raw `video_status` strings (only the closed enrichment enum appears)
- any container or host path

Remediation: remove `file_path` from the DITrack response schema now, sweep every response schema for
path-typed and job-internal fields, and add an invariant/contract test so the exclusion is enforced by
absence, not by trust.

### 4.5 Unlisted - reachable by link

Unlisted (owner decision) is the deliberate, bounded exception whose safety rests on id
non-guessability:

- counts as **published** for the rerun block (section 2.6) - it has live, embeddable direct links;
- **noindexed** - `X-Robots-Tag: noindex` on unlisted pages and media, excluded from listings/sitemaps;
- **embeddable by direct UUID** - reachability by direct id is its product semantic, resting on UUID
  non-guessability (UUIDs, never sequential ids);
- **no auth wall in v1** - unlisted is unlisted-but-reachable (security by unguessable URL, not access
  control), distinct from private (which is auth-gated).

### 4.6 Caching and nginx bypass

Origin (nginx) serving only in v1. Public media may carry modest cache headers; unlisted media must not
be indexed; private media is never cacheable. Because visibility is revocable, there is no long-lived
public caching until the deferred CDN/object-storage decision revisits revocation. nginx must not expose
the storage mount via any static location that bypasses the handler (confirm no static location over
`/app/storage`).

---

## 5. Video enrichment object and deferral (ADR-0007)

Video composition stays wholly out of the v1 ship gate. The reservation is contractual and structural,
not schematic - fixing the enrichment object shape, the enum, the version binding, and the job-tree slot
now is what makes video land additively later with zero migration to the manifest table, zero change to
the public gate predicate, and zero change to the finalise transaction.

### 5.1 The read-payload video object

Optional enrichment object in the read payload: `video: {url, state}`.

- `state` is drawn from the closed in-code enum `absent | processing | ready | failed`.
- `url` is opaque-id-based and present only when `state = ready`.
- In v1, `video.state` = `absent` by construction (it is the projection of "no VIDEO_COMPOSE job exists
  for this render_version", and no video job is ever created in v1).
- Identical for the Astro island and the app route.

The **immutable manifest payload (schema_version 1) carries no video fields**. Reserving slots in an
immutable snapshot for an artefact produced after the snapshot is written is incoherent; forward
compatibility is carried by `schema_version`, not by empty keys. Montage and video URLs live only in the
read-payload enrichment section.

### 5.2 Version-scoped storage and job slot

- **Version binding.** Video enrichment is keyed to `(shootout_id, render_version)`. The path convention
  `STORAGE_BASE/<shootout_id>/v<N>/` includes the future video output; a VIDEO_COMPOSE job may write only
  inside its own version directory and may never touch a file referenced by any existing manifest.
- **Job-tree slot.** VIDEO_COMPOSE is reserved as a non-gating enrichment child dispatched after
  SHOOTOUT_FINALISE (a sibling of the demoted montage), reporting terminal state through the
  reconciliation choke-point, never counted by the COMPLETED barrier.
- **Serving.** When video lands, its media resolves through the same opaque-id, visibility-plus-lifecycle
  checked handler as audio; the public gate predicate is unchanged.
- **Columns.** `Shootout.video_path` survives as a version-scoped enrichment pointer. The free-String
  `video_status` and `video_job_id` columns stop being authorities and are rationalised in the
  baseline/ORM drift-cleanup pass.

### 5.3 Out of the v1 gate

Fully deferred: all VIDEO_COMPOSE execution and the Remotion/video-worker pipeline; the video-worker
internals read-in; video terminal-path hardening; video media serving and any video URL in the public
payload; video SEO markup (VideoObject and similar); and any dependency of the montage decision on video
(the montage is retained on its own merits). Because no VIDEO_COMPOSE job runs in v1, there is no video
stranding surface at all.

### 5.4 Reopen trigger

Video composition reopens only when both structural preconditions hold **and** at least one demand
signal fires: `P1 AND P2 AND (D1 OR D2 OR D3)`.

- **P1** (audio A/B live) - the first public shootout pages are serving from manifests in production with
  G1-G4 landed.
- **P2** (event-state substrate closed) - the event-state blocking amendments are landed (reconciliation
  closed over the full terminal set, master-failure projection, every terminal writer routed through the
  choke-point, reaper/heartbeat fix). VIDEO_COMPOSE is a new terminal-state writer and must plug into a
  closed projection, not the currently holed one.
- **D1** (distribution commitment) - a product decision to publish GTS content on a video-native channel
  (YouTube/Shorts, embed partner).
- **D2** (user pull) - sustained explicit requests for video export/embed. Placeholder threshold: five
  distinct requesters within a rolling 30 days; calibrate to actual traffic.
- **D3** (share evidence) - share instrumentation shows video-first destinations among the top share
  targets, or audio-only links measurably underperforming there. Placeholder pending instrumentation.

Explicit non-triggers: the video-worker code existing; the montage "wanting a consumer"; a single
anecdotal request; uninstrumented SEO speculation.

D2/D3 thresholds are product-calibrated placeholders; the trigger structure does not depend on the
numbers. On firing, the first task is the video-worker/Remotion read-in (does it consume `master.wav` or
per-chain segments), which shapes the fast-follow but is not itself a trigger condition. Backfill of
existing published shootouts on reopen, and in-place re-cuts of a published shootout's video, are both
deferred to reopen; re-cuts default to being treated like reruns (blocked while published) unless a
versioned video path is added at that point.
