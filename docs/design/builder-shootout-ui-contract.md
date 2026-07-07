# Builder and shootout UI contract

Field-level engineering contract for the signal-chain builder on the `/app` SPA and its complete
attachment to the job system: assemble, trigger, observe, finalise, compare. It composes with the
two existing authorities and never restates them: the job system's state machine, timing, and
idempotency are `docs/design/job-system-contract.md`; the artefact model, manifest storage, public
gate, and wire allow-list are `docs/design/shootout-artefact-contract.md`. Decisions behind this
contract: ADR-0001 (SPA app surface), ADR-0003/0004/0005/0006 (via the artefact contract),
ADR-0008 (DI Library). This document is declarative: it states what the builder-to-job attachment
IS once the builder units land. Deviations are bugs.

## Scope decisions this contract encodes (settled 2026-07-07)

- **Captures-only, NAM+IR only.** A chain block is a `user_gear_id` capture reference. The v1
  renderable platform set is `{nam, ir}`; every other `Platform` value is greyed out client-side
  and rejected 422 server-side. `full_rig` and `outboard` gear types are outside the v1 template.
- **The POC template is fixed**: DI → FX slot → AMP slot → CAB slot, in signal order. There is no
  post-effect stage in v1 and no stage reordering; the only ordering that exists is option order
  within a slot. FX options are `pedal` captures, AMP options are `amp` captures, CAB options are
  `ir` captures.
- **Assemble-in-place.** The builder is the shootout draft. One assembly request carries the DI
  and the slot structure; the server expands the combination matrix and creates the shootout plus
  its chains in one transaction. `SignalChain` rows created by assembly are internal
  materialisations satisfying the schema, not user-library artefacts; the My Chains library flow
  is not part of the run path.
- **Server-side guidance authority.** The chain grammar lives in the domain validator, exposed by
  the guidance endpoint (section 1.5). The SPA never encodes grammar.
- **Polling transport** behind one TanStack Query hook (section 3). SSE is a later swap behind
  the same hook.
- **Player MVP interaction set** is play/pause/seek, a chain list, playhead-preserving chain
  switching, and the active chain's waveform (section 5). Nothing else.

## 1. Builder state model

Owned by `frontend/app`; headless and testable, no visual components. The store library is chosen
at implementation time; the types and transitions below are the contract regardless of store.

### 1.1 Core types

```ts
type SlotKind = 'fx' | 'amp' | 'cab';

/** The one renderable-platform authority on the client, mirrored from the server's 422 rule. */
const RENDERABLE_PLATFORMS = ['nam', 'ir'] as const;

interface SlotOption {
  /** Client-local stable id; survives reorders; maps 422 errors back to UI rows. */
  optionId: string;
  /** Always present. Catalogue picks resolve through auto-add (1.4) BEFORE insertion. */
  userGearId: string;
  gearType: 'pedal' | 'amp' | 'ir';
  displayName: string;        // UserGear.nickname ?? Gear.name, display only
  platform: 'nam' | 'ir';     // display only; server re-derives, never trusts this
  gearId: string;             // catalogue ref, drives the option icon
}

interface Slot {
  kind: SlotKind;
  options: SlotOption[];      // order = user order (drag within slot), drives matrix order
  /** FX only: adds a "no pedal" combination to the matrix. Invariant: false on amp/cab. */
  includeNone: boolean;
}

interface DiSelection {
  diTrackId: string;
  displayName: string;
  durationSeconds: number;
  /** ADR-0008: 'own' tracks stream for audition; 'shared' tracks audition by waveform + metadata only. */
  source: 'own' | 'shared';
}

interface ChainDraft {
  name: string;               // required at Run; collected in the Run confirm popover
  description: string | null;
  di: DiSelection | null;
  slots: { fx: Slot; amp: Slot; cab: Slot };
}
```

There is exactly one option shape. A block without a resolvable `userGearId` cannot enter the
draft — the auto-add seam (1.4) enforces this structurally, and the server enforces it again at
assembly. Nothing is ever silently dropped.

### 1.2 UI and run state

```ts
interface BuilderUiState {
  selection: { slot: SlotKind; optionId: string } | null;  // drives the detail panel
  browserScope: SlotKind | 'di' | null;                    // drives the docked Gear Browser
  dirty: boolean;
}

type RunState =
  | { phase: 'idle' }
  | { phase: 'assembling' }                                 // POST /api/shootouts in flight
  | { phase: 'observing'; shootoutId: string; parentJobId: string };
```

`RunState` is a discriminated union; ids exist only in `observing`. On successful trigger the SPA
navigates to `/app/shootouts` (newest at top, pending) and the polling hook (section 3) takes
over; the builder returns to `idle` with the draft cleared.

### 1.3 Matrix expansion (pure function)

```ts
interface MatrixCombination {
  index: number;              // 0-based; becomes ShootoutChain.position
  label: string;              // display-name join, " + " separated, none omitted
  fx: SlotOption | null;      // null = the includeNone combination
  amp: SlotOption;
  cab: SlotOption;
}
function expandMatrix(slots: ChainDraft['slots']): MatrixCombination[];
```

- Expansion is nested iteration in template order — fx outermost, amp, cab innermost (cab varies
  fastest). FX ordering is `options` order with the `includeNone` combination last.
- FX factor = `options.length + (includeNone ? 1 : 0)`, minimum 1 (an empty FX slot means no FX
  stage in any chain, factor 1). AMP and CAB factors = `options.length`, each ≥ 1 to run.
- Cap: `2 <= combinations.length <= 16` (ADR-0003). The client mirrors the cap for the Run gate
  and the bottom-bar summary; the server's 422 is the authority.
- The server performs the identical expansion at assembly; the assembly response's chain list is
  index-aligned with `expandMatrix` output by construction, which is what lets the SPA map
  per-chain job progress back to matrix rows (section 3.3).

Run gate (all required): `di != null`, `amp.options.length >= 1`, `cab.options.length >= 1`,
cap satisfied, guidance `is_complete` (1.5), `phase == 'idle'`. The Run button in the bottom bar
opens a confirm popover (name required, description optional, matrix summary) and then assembles
and triggers as two sequential calls (section 2).

### 1.4 Auto-add seam (consumes `BLD-autoadd-library`)

Selecting a catalogue result in the Gear Browser calls the resolve-or-create endpoint
(`gear_model_id` → caller's `UserGear` row, idempotent per its `(user_id, gear_model_id)` unique
constraint) and only then constructs the `SlotOption` from the response. The builder never holds
a catalogue-only block; the legacy dual-source `{tone, user_gear_id?}` shape and the
`gearItemToTone()` projection do not exist in the SPA.

### 1.5 Guidance consumption (consumes `BLD-guidance-endpoint`)

`POST /api/signal-chains/guidance` is the grammar authority. Request/response (typed in the
OpenAPI schema; the SPA uses generated types):

```
GuidanceRequest  { blocks: [{ gear_type: 'pedal' | 'amp' | 'ir' }] }
GuidanceResponse { next_valid_gear_types: string[], guidance_message: string, is_complete: bool }
```

The SPA projects the draft to its template signature — one representative block per non-empty
slot, in template order (fx, amp, cab) — and submits it via one TanStack Query hook (ported
legacy hook: signature-as-query-key, `staleTime` 1s, previous data as placeholder). Client-side
logic is limited to the empty-draft default (`next_valid_gear_types: ['pedal','amp']`, not
complete) and the mapping `pedal → FX addable`, `amp → AMP addable`, `ir → CAB addable`.
`post_effect` and `full_rig` do not appear in v1 requests or affordances.

### 1.6 Error surface

Assembly 422s carry per-option JSON-pointer locations
(`slots.amp.options[1].user_gear_id`); the store maps them back to `optionId` by index and the
canvas renders the error on the offending option chip. Transport/5xx errors surface on the Run
popover with the draft intact; `assembling` always resolves back to `idle` on failure. There is
no partial-assembly state: the server creates the shootout transactionally or not at all.

## 2. Assembly API (consumes `API-shootout-assembly`)

All endpoints require session auth via `get_current_user_required` — the module-local
`get_current_user` test stubs in `shootouts.py` and `jobs.py` are replaced by the real dependency
(today those routers 401 in production). All are owner-scoped: a non-owned id is a uniform 404.

### 2.1 `POST /api/shootouts` — assemble the draft

Replaces the current chain-less create; there is one create shape.

```
ShootoutAssembleRequest {
  name:          str (1..255)
  description:   str | null
  di_track_id:   UUID
  slots: {
    fx:  { options: [{ user_gear_id: UUID }], include_none: bool }
    amp: { options: [{ user_gear_id: UUID }] }   // 1..16
    cab: { options: [{ user_gear_id: UUID }] }   // 1..16
  }
}
```

Validation (422 with per-field locations, evaluated fully — all errors reported, not first-only):

- Every `user_gear_id` resolves to a `UserGear` row owned by the caller (auto-add has already
  materialised catalogue picks). The server re-derives gear type and platform through
  `UserGear → GearModel → Gear`; client display fields are never trusted.
- Slot typing: fx options are `gear_type = pedal`, amp options `amp`, cab options `ir`.
  `full_rig`, `outboard`, and any other gear type are rejected.
- Platform: `GearModel.platform` must be `nam` (fx, amp) or `ir` (cab) — the v1 renderable set.
- `include_none` is accepted on fx only.
- DI: `di_track_id` resolves to a track the caller may attach — their own, or a shared-pool track
  per ADR-0008. Matrix cap: expanded combination count in `2..16`.

Behaviour, one transaction: expand the matrix exactly as section 1.3 defines; create the
`Shootout` (status DRAFT, `render_version` 1) and, per combination, an internal `SignalChain`
(platform `nam`, blocks in signal order fx→amp→cab with 0-indexed positions) plus a
`ShootoutChain` (`position` = combination index, `label` = combination label). Assembly-created
signal chains are not surfaced by the My Chains library listing. `Shootout.MAX_CHAINS` is aligned
20 → 16 in the domain entity; the wizard HTMX path retires when this lands.

**DI FK semantics.** `Shootout.di_track_id` moves from `ondelete=CASCADE` to `ondelete=SET NULL`
(migration in this unit). CASCADE contradicts ADR-0008's attach-time snapshot rule — deleting a
DI track must never destroy shootouts built on it. Post-publication the manifest carries the DI
descriptors; a DI deleted while a draft/run is in flight fails that render with a normal FAILED
job, never a row cascade.

Response `201 ShootoutDraftResponse` (also the `GET /api/shootouts/{id}` shape):

```
ShootoutDraftResponse {
  id: UUID, name: str, description: str | null,
  status: 'draft' | 'pending' | 'processing' | 'completed' | 'failed',
  render_version: int, di_track_id: UUID | null, created_at: datetime,
  chains: [ { id: UUID, position: int, label: str,
              blocks: [ { position: int, user_gear_id: UUID, gear_type: str } ] } ]
}
```

`ShootoutResponse` loses `is_processed` and `output_path` (status replaces the former; the latter
is an absolute exclusion per the artefact contract §4.4) and gains `status`/`render_version`.
The list endpoint (`GET /api/shootouts/`) returns the same shape minus `chains`, plus
`chain_count: int`, ordered `created_at` descending — the `/app/shootouts` stack query.

Assembly is a plain create, not idempotent: a repeated POST creates a second DRAFT. The Run
popover disables its submit while `assembling`; stray drafts are visible in the stack and
deletable (`DELETE /api/shootouts/{id}`, 204, drafts and terminal shootouts only — deleting a
PENDING/PROCESSING shootout is 409).

### 2.2 `POST /api/shootouts/{id}/process` — trigger

Kept as-is with two contract corrections: wrong-state is `409` (was 400) and the router uses real
auth. Guards: owner 404; `status == DRAFT` else 409. Behaviour is the job-system contract's
transactional outbox: create the parent SHOOTOUT job, flip shootout DRAFT → PENDING, enqueue —
one transaction. Response `202 { job_id: UUID }`. The status flip makes the trigger naturally
idempotent-by-state: a repeat is 409, never a second job tree.

## 3. Run/observe projection

### 3.1 Jobs API corrections

`JobResponse` is corrected so shootout jobs can actually serialise and the tree is observable:

- `job_type` becomes the full `JobType` value set (today's Literal omits `shootout`,
  `shootout_audio`, `shootout_master`, `shootout_finalise` — a shootout job fails response
  validation).
- `parent_job_id: UUID | null` is added.
- `result_path` and `task_id` are removed — storage paths and internals are absolute exclusions
  in all payloads (artefact contract §4.4). Nothing in the SPA consumes them.
- `error: str | null` stays: the authenticated jobs API is the owner's operational channel
  (artefact contract §3.2); the exclusion list binds the shootout read payload and public
  surfaces, not this endpoint.
- Invalid `?status=`/`?job_type=` query values are 422, not an unhandled ValueError.

`GET /api/jobs/{job_id}` returns the job with one level of children embedded, ordered by
`created_at`:

```
JobResponse {
  id, job_type, status, progress: int, message: str | null, error: str | null,
  entity_id: UUID | null,          // SHOOTOUT: shootout id; SHOOTOUT_AUDIO: shootout_chain id
  parent_job_id: UUID | null,
  created_at, updated_at,
  children: [JobResponse]          // empty for leaf jobs; children's own `children` always []
}
```

### 3.2 The polling hook

One TanStack Query hook, `useShootoutRun(parentJobId)`, is the only job-status consumer:

- Polls `GET /api/jobs/{parentJobId}` at a fixed 2000 ms interval while the parent is
  non-terminal; `refetchOnWindowFocus` on. No backoff: renders are bounded and the job system
  guarantees terminality (reaper + bounded retry), so the hook needs no client-side timeout.
- Stops when `parent.status` enters the terminal set `{completed, failed, cancelled,
  dead_lettered}` (job-system contract). Resumes on a retry action (below).
- SSE later replaces the interval inside this hook; consumers see the same shape.

### 3.3 Per-chain progress mapping

Children with `job_type = shootout_audio` map to matrix rows by `entity_id` =
`ShootoutChain.id`, joined against the assembly response's `chains` (section 2.1). Display
projection of child status: `pending | queued → queued`, `running → rendering`,
`completed → done`, `failed | cancelled | dead_lettered → failed`. The `shootout_finalise` child
surfaces as a single "publishing" row once all audio children are done; `shootout_master` is
non-gating enrichment and is not displayed in v1. Parent `progress` is the reconciler's
percent-of-children-complete and drives the stack row's progress bar.

Parent `completed` implies the manifest is written (the finalise handler completes the parent in
the manifest transaction — job-system contract, Finalise), so the terminal transition to
`completed` is the signal to fetch the artefact payload (section 5) and swap the stack row to the
player affordance. Parent `failed` renders the retry affordance.

### 3.4 Retry affordance

For each child in `failed` status the UI offers retry via the existing
`POST /api/jobs/{child_id}/retry` (409 unless FAILED; routes through the transition service,
which re-projects the parent and shootout out of FAILED per the job-system contract). The hook
restarts polling on a successful retry response. `dead_lettered` children are poison messages
needing admin redrive: the UI shows them as terminally failed with no retry affordance. Retry is
per-child; there is no parent-level retry (re-enqueueing the parent would fan out no new work —
children exist and FAILED children are not PENDING).

## 4. SHOOTOUT_FINALISE payload (consumes `DOM-shootout-finalise`)

Mechanics (exactly-once guard, transaction contents, montage dispatch) are the job-system
contract's Finalise section and artefact contract §2.5; storage shape is §2.1–2.3. This section
fixes the field-by-field payload the handler assembles, with sources. `schema_version` 1.

```
{
  "schema_version": 1,
  "shootout": {
    "id":          str(Shootout.id),
    "title":       Shootout.name,
    "description": Shootout.description,                    // null allowed
    "creator":     { "username": User.username, "avatar_url": User.avatar_url },  // via Shootout.user_id
    "created_at":  Shootout.created_at, ISO-8601 UTC
  },
  "di": {                                                    // via Shootout.di_track_id (DITrack)
    "name":             DITrack.name,
    "guitar":           DITrack.guitar,                      // null allowed
    "pickup":           DITrack.pickup,                      // null allowed
    "tuning":           DITrack.tuning,                      // null allowed
    "duration_seconds": DITrack.duration_seconds
  },
  "timeline": { "aligned": "start", "duration_seconds": max(chains[].duration_seconds) },
  "chains": [                                                // ordered by ShootoutChain.position, length 2..16
    {
      "label":            ShootoutChain.label,
      "media_path":       "v<version>/<shootout_chain_id>.wav",   // storage-relative, INTERNAL, stripped at wire projection
      "segment_id":       str(AudioSegment.id),                    // INTERNAL, stripped at wire projection
      "duration_seconds": AudioSegment.duration_seconds,
      "waveform":         AudioSegment.waveform,                   // display envelope
      "integrated_lufs":  AudioSegment.integrated_lufs,
      "peak_dbfs":        AudioSegment.peak_dbfs,
      "provenance": [                                        // ordered by SignalChainBlock.position
        {
          "position":      SignalChainBlock.position,
          "gear_type":     "pedal" | "amp" | "ir",           // SignalChainBlock.gear_type
          "display_name":  UserGear.nickname ?? Gear.name,
          "platform":      GearModel.platform value ("nam" | "ir"),
          "icon_asset_id": str(Gear.id)                      // stable asset ref; surfaces resolve imagery from it
        }
      ]
    }
  ]
}
```

Rules:

- **Segment pinning.** Per chain, select the `AudioSegment` where `(shootout_chain_id, version =
  Shootout.render_version)` — exactly one by the unique constraint. A missing segment fails the
  finalise job (normal FAILED path, retryable); a partial manifest is never written.
- **Provenance is joined at finalise time** (`SignalChainBlock → UserGear → GearModel → Gear`)
  and snapshotted. An unresolvable join (gear removed between render and finalise) fails the
  finalise job with an error naming the chain and block position; the payload never carries
  fabricated or placeholder provenance.
- **No `parameters` key.** Captures-only: schema_version 1 provenance blocks carry no parameter
  settings. Editable parameters return as a designed feature with a `schema_version` bump —
  forward compatibility by version, not empty keys (artefact contract §2.3/ADR-0007 principle).
- **No montage/video fields** in the payload (artefact contract §2.3); no job fields, no user
  ids, no absolute paths anywhere in it.
- **Gate fields.** The manifest row's existence is itself the public-linking gate input (G1); the
  interim published-predicate is `manifest exists AND status = COMPLETED` until the visibility
  column lands (artefact contract §2.6). The payload carries no gate fields.

## 5. Comparison player data contract

### 5.1 What the player fetches

`GET /api/shootouts/{id}/artefact` returns the wire read payload — the allow-list projection of
the latest manifest defined field-by-field in artefact contract §4.4, with `media_url` per chain
assembled from the pinned segment as an opaque id-based URL (§4.2). This contract adds only:

- **Gating.** The joint public predicate per §4.1 on every request; additionally the
  authenticated owner may fetch their own artefact regardless of visibility (owner preview).
  Everything else is the uniform 404 (§4.3).
- **Version.** The served manifest is the highest `version` for the shootout (exactly one in v1
  under the rerun block).
- **Opacity.** Clients treat `media_url` (and `montage_url`) as opaque strings; the URL scheme is
  owned by the public media handler unit (`DOM-public-media-handler`). No client constructs or
  parses media URLs.

One payload shape serves both mounts of the one player component (ADR-0001): the Astro island on
`/shootouts/:id` and the `/app` route component.

### 5.2 Player MVP behaviour

- One shared timeline of `timeline.duration_seconds`; chains are start-aligned by construction
  (artefact contract §1), so switching is a pure source swap at the preserved position.
- Interaction set: play/pause, seek, select chain from the chain list (label + provenance), and
  the active chain's waveform rendered from the payload's `waveform` envelope. Chain switch
  preserves the playhead: pause A, seek B to `currentTime`, play B. Nothing else in v1 — no loop
  region, no blind mode, no montage playback, no metrics, no gain controls (segments are
  normalised to -14 LUFS; `integrated_lufs`/`peak_dbfs` are display metadata).
- Media loading: one `HTMLMediaElement` per chain, `preload="none"` until first activation;
  decoded-buffer (WebAudio) playback is out of scope for v1 (16 decoded segments would not fit a
  sane memory budget).
- A chain whose media errors renders an inline failed state in the chain list; the player never
  blocks the other chains on one failed source.

### 5.3 Legacy cutover (consumes `FE-master-compat-cutover`)

The Astro shootout-detail player migrates off `Shootout.output_path` onto this artefact payload
and per-chain segments. `GET /api/shootouts/{id}/audio/master` survives solely as an owner
montage-download compatibility route until no page or embed depends on the old binding; it never
feeds the player. The owner-only per-chain streaming endpoint
(`/chains/{chain_id}/audio`) is superseded by manifest-resolved media and retires with the
cutover (its `segments[0]` pick is nondeterministic after rerun and reads live rows the artefact
contract forbids as a serving path).

## 6. Component migration table

Dispositions for the legacy `frontend/astro/src/components/SignalChain/` directory (settled
2026-07-07). Generic primitives target the design-system repo (vendored back per ADR-0001); GTS
compositions target `frontend/app/src/features/builder/`.

| Legacy component | Disposition | Target |
|---|---|---|
| `types.ts`, `useBuilderState.ts` | Rebuild | `frontend/app` builder store (section 1 types; slot model replaces the five-stage reducer) |
| `useSignalChainGuidance.ts` | Port logic | `frontend/app` guidance hook on generated types (1.5) |
| `OutputMatrix.tsx` expansion logic | Port as pure function | `expandMatrix` in the builder store (1.3), 16-cap added |
| `OutputMatrix.tsx` preview UI | Rebuild on Dense | bottom-bar matrix summary + expandable list |
| `SignalChainBuilder.tsx` shell | Drop | replaced by the decided layout (docked browser / linear canvas / detail panel / bottom bar) |
| `ToneSearchModal.tsx` | Rebuild | GearBrowser docked composition (FilterPanel + SearchInput + DataList), slot-scoped; `gearItemToTone()` dies with auto-add |
| `DITrackSelectModal.tsx` | Rebuild | DI picker per ADR-0008 (own tracks stream; shared pool auditions by waveform/metadata); raw-fetch path dies |
| `SaveChainDialog.tsx` / `stateToApiBlocks` | Drop | assembly flow (section 2) replaces save-to-library in the run path |
| `SortableBlock.tsx` | Port | design-system generic dnd primitive; within-slot option reorder |
| `SortableStageColumn.tsx`, `StageColumn.tsx`, `ConnectionLine.tsx` | Drop | column model does not survive the linear canvas |
| `BlockCard.tsx`, `AmpBlock.tsx`, `CabinetBlock.tsx`, `DITrackBlock.tsx` | Rebuild on Dense | one option-chip/card component (the amp/cab twins collapse); DI node card |
| `EffectBlock.tsx` + its `index.ts` re-exports | Drop (dead params-era code, zero importers) | removed in `BLD-params-purge` |

## Enforcement

- The SPA consumes generated OpenAPI types only (`just gen-app-api`; `check-app-api` gates
  drift). No hand-written DTOs for any endpoint in this contract.
- A response-schema sweep test asserts the absolute exclusions of artefact contract §4.4
  (`file_path`, `output_path`, `result_path`, `task_id`, storage paths) are absent from every
  schema this contract touches — enforced by absence, not trust.
- A round-trip invariant test: assemble → GET returns chains index-aligned and content-identical
  with the client `expandMatrix` for the same draft.
- A cap test pins `Shootout.MAX_CHAINS == 16` and the assembly 422 at 17 combinations; the
  client mirrors the constant for UX only, the server 422 is the authority.
- The structural guard and timing tests of the job-system contract are unchanged and continue to
  bind every path this contract adds (assembly trigger, retry, finalise).
