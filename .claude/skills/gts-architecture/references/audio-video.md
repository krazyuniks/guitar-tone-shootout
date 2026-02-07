# Audio & Video Processing

Audio processing transforms DI tracks through signal chains to produce audio segments. Implemented in `libs/audio/`.

## Output

**Audio segment:** Processed output from running a DI track through a signal chain with a preset. Segments can be:
- Played standalone (signal chain library)
- Grouped into comparison video (parent job orchestrates)

## Processing Pipeline

Signal flow through blocks:

```
DI Track (WAV mono)
    ↓
Resample (if sample rate mismatch)
    ↓
[Pre-Effect Blocks]* (highpass, compressor, overdrive, etc.)
    ↓
Amp Block (NAM model -- HEAD or FULL_RIG)
    ↓
[Loop Effect Blocks]* (EQ, modulation -- NOT allowed if FULL_RIG)
    ↓
[IR Block]? (cabinet convolution -- required for HEAD, forbidden for FULL_RIG)
    ↓
[Post-Effect Blocks]* (reverb, delay, etc.)
    ↓
LUFS Normalization (EBU R128)
    ↓
Output WAV (mono, 48kHz)
```

**Block execution:** Each block processes audio sequentially. Block parameters come from the preset, which stores gear-specific settings (e.g., parametric EQ with 3 bands vs graphic EQ with 10 bands).

**FULL_RIG constraint:** FULL_RIG amps have cabinet baked in. Loop blocks and IR block are forbidden -- audio flows directly from amp to post-effects.

## Block Execution

Blocks are processed through their respective engines. Consecutive blocks on the same engine may be batched.

**Processing engines:**

| Engine | Block Types | Notes |
|--------|-------------|-------|
| Pedalboard | Built-in effects (EQ, compressor, delay, reverb, filters), IR convolution | Supports stereo |
| NAM/PyTorch | Amp captures, pedal captures | Outside Pedalboard |

**Current approach:** NAM/PyTorch blocks run independently, Pedalboard handles effects and IR convolution. This works -- audio quality is good.

**Batching:** Consecutive Pedalboard blocks could run as a single chain to reduce overhead. Requires experimentation to verify no sound quality impact. If issues arise, simplify chain rules.

**Swappability:** Engine selection is behind an adapter interface (`AudioProcessor` protocol). Pedalboard is the default; alternatives (LSP IR, other DSP libraries) can be swapped without changing domain logic.

**Implementation note:** Existing audio processing tests provide a foundation for experimenting with block ordering and batching strategies.

## NAM Model Execution

Neural Amp Modeler inference via PyTorch and the `nam` library.

**Model format:** `.nam` files (JSON configuration + weights)

**Loading:**
1. Parse JSON config from `.nam` file
2. Initialize PyTorch model via `nam.models.init_from_nam()`
3. Set to eval mode (inference only)

**Processing:**
```python
# Input: float32 numpy array (mono)
# Output: float32 numpy array (mono)
model(audio_tensor, pad_start=True)
```

**Caching:** Models cached in memory (LRU) to avoid repeated loading. Critical for permutation processing where the same amp processes multiple DI tracks.

**Sample rate:** Models report native sample rate. Audio resampled to match if needed.

## Loudness Normalization

EBU R128 loudness normalization ensures consistent playback volume across segments.

**Library:** `pyloudnorm` (ITU-R BS.1770 standard)

**Process:**
1. Measure integrated loudness (LUFS) of processed audio
2. Calculate gain adjustment to reach target
3. Apply gain

**Default target:** -14.0 LUFS (streaming platform standard)

**Silent audio:** Fails the job. Silent input indicates a problem (missing model output, corrupt DI track). Failure propagates through job pipeline to user notification and observability stack (Loki).

**Why normalize:** A/B comparisons require matched loudness. Louder audio is perceived as "better" -- normalization removes this bias.

## Permutation Processing

Signal chain groups generate multiple audio segments by varying gear selections across blocks.

**What multiplies permutations:**

| Block Type | Can Multiply | Can Be Null | Example |
|------------|--------------|-------------|---------|
| DI Track | Yes | No | [DI1, DI2] |
| Pre-Effect / Pedal | Yes | Yes | [(null, Overdrive)] or [(OD1, OD2)] |
| Amp (HEAD/FULL_RIG) | Yes | No | [Amp1, Amp2] |
| Loop Effect | Yes | Yes | [(null, EQ)] |
| IR | Yes | No | [IR1, IR2] (HEAD only) |
| Post-Effect | Yes | Yes | [(null, Reverb)] |

**Null gear:** Represents "no gear in this position". Allows A/B comparison of chain with vs without an effect. Amps and IRs cannot be null -- they're required chain components.

**Permutation expansion example:**

```
SignalChainGroup
├── DI Tracks: [DI1]
├── Pre-Effects: [(null, Overdrive)]      <- 2 options (with/without)
├── Amps: [Amp1 (HEAD)]
├── Loop Effects: [EQ]                     <- 1 option (static)
├── IRs: [IR1, IR2]                        <- 2 options
└── Post-Effects: [Reverb]                 <- 1 option (static)

Permutations: 1 x 2 x 1 x 2 x 1 = 4

├── DI1 -> (none) -> Amp1 -> EQ -> IR1 -> Reverb
├── DI1 -> (none) -> Amp1 -> EQ -> IR2 -> Reverb
├── DI1 -> OD -> Amp1 -> EQ -> IR1 -> Reverb
└── DI1 -> OD -> Amp1 -> EQ -> IR2 -> Reverb
```

**Limits:**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max permutations | 27 | Keeps processing time reasonable |
| Max options per block | 3 | UI/UX simplicity |

Total permutations = product of all block option counts. Validated before processing.

## File Formats & Quality

**Input:**

| Type | Format | Constraints |
|------|--------|-------------|
| DI Track | WAV mono | Any sample rate (resampled if needed) |
| NAM Model | `.nam` (JSON) | Must match expected schema |
| IR | WAV mono | <=2 seconds, 44.1/48/96 kHz |

**Output:**

| Type | Format | Settings |
|------|--------|----------|
| Audio segment | WAV mono | 48 kHz, float32 internal, 16-bit PCM saved |

**Sample rate:** 48 kHz standard (video compatibility). Input audio resampled via Pedalboard if mismatched.

**Bit depth:** Float32 throughout pipeline for headroom. Final output saved as 16-bit PCM (sufficient for playback, smaller files).

## Error Handling

**Validation errors (fail fast):**

| Error | Cause | Response |
|-------|-------|----------|
| `FileNotFoundError` | DI track, model, or IR missing | Job fails, user notified |
| `NAMLoadError` | Invalid `.nam` file or model init failure | Job fails with details |
| `IRValidationError` | Stereo IR, duration >2s, unreadable | Job fails with details |
| `InvalidChainError` | HEAD without IR, FULL_RIG with IR, etc. | Rejected at submission |

**Processing errors (may retry):**

| Error | Cause | Response |
|-------|-------|----------|
| `ProcessingError` | PyTorch/Pedalboard failure | Retry up to max attempts |
| `NormalizationError` | Silent audio, invalid LUFS | Job fails, user notified |

**Partial failure:** If one permutation fails in a group, others continue. Parent job reports partial completion with failed segment details.

## Video Generation

Video composition combines audio segments into comparison videos. Implemented in `libs/audio/video/`.

### Purpose

Videos enable side-by-side tone comparisons:
- Sequential playback of each tone
- Visual waveforms for each segment
- Labels identifying gear used
- YouTube chapter markers for navigation

### Composition Pipeline

```
Audio Segments + Metadata
    ↓
Generate waveform visualizations (per segment)
    ↓
Render title card (gear list, DI track info)
    ↓
Compose video frames (waveform + labels)
    ↓
Concatenate segments with transitions
    ↓
Encode final video (MP4)
    ↓
Generate chapter data (for YouTube)
```

### FFmpeg

Video composition uses FFmpeg for:
- Waveform visualization generation
- Frame composition and text overlay
- Audio/video muxing
- Final encoding

**Output format:** MP4 (H.264 video, AAC audio) -- universal playback support.

### Segment Metadata

Each audio segment carries metadata for video composition:

| Field | Purpose |
|-------|---------|
| `segment_id` | Unique identifier |
| `label` | Display name (e.g., "Amp1 + IR2") |
| `start_time` | Position in final video |
| `duration` | Segment length |
| `gear_info` | Amp, IR, effects used |

### Job Hierarchy

Video generation is a child job of SHOOTOUT:

```
SHOOTOUT (parent)
├── SHOOTOUT_AUDIO (tone A)
├── SHOOTOUT_AUDIO (tone B)
├── SHOOTOUT_AUDIO (tone C)
└── VIDEO_COMPOSE (after all audio complete)
```

VIDEO_COMPOSE waits for all SHOOTOUT_AUDIO jobs to complete before starting.

### Current State

| Feature | Status |
|---------|--------|
| Waveform visualization | Exists |
| Gear labels | Exists |
| Gear images | Exists |
| Video layout | Exists (basic) |
| Chapter markers | Exists |

### Implementation Notes

Layout and visual refinements will be done interactively during implementation. The foundation works -- aesthetic improvements are iterative.
