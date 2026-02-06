# Domain Model

GTS ubiquitous language - our terminology for the domain.

## Overview

Guitar Tone Shootout is an A/B testing platform for guitar tones. Users compare audio samples processed through different gear configurations to evaluate tone quality.

### Core Value Proposition

The platform's unique value is **gear comparison through audio processing**. Users build signal chains from amp captures and IRs, process their DI recordings through these chains, and compare results side-by-side in video format.

Gear comes from multiple sources:
- **Tone3000 (T3K)** -- NAM amp/pedal captures and IRs (largest volume)
- **Community uploads** -- User-contributed IRs
- **Future sources** -- AIDA-X, other marketplaces

All sources feed into a unified gear model for consistent handling.

### Signal Chain: The Foundation

The signal chain is the core domain concept. It defines how audio flows through gear:

```
DI Track -> [Pre-Effects*] -> Amp -> [Loop Effects*] -> [IR?] -> [Post-Effects*] -> Output
                                        ^
                              (not allowed if FULL_RIG)
```

| Component | Required | Quantity | Description |
|-----------|----------|----------|-------------|
| DI Track | Yes | 1 | Clean guitar recording (input) |
| Pre-Effects | No | 0+ | Overdrive, distortion, fuzz, wah, compressor, boost |
| Amp | Yes | 1 | Either HEAD (requires IR) or FULL_RIG (IR baked in) |
| Loop Effects | No | 0+ | Effects between amp and cabinet (EQ, modulation); not allowed with FULL_RIG |
| IR | Conditional | 0-1 | Cabinet simulation; required for HEAD, forbidden for FULL_RIG |
| Post-Effects | No | 0+ | Delay, reverb, spatial effects |

## Aggregate Roots

| Aggregate | Description |
|-----------|-------------|
| **User** | Authenticated user account with linked OAuth identities |
| **Gear** | Equipment item (amp, pedal, IR, etc.) - unified across all sources |
| **DITrack** | Uploaded guitar recording (source audio for processing) |
| **SignalChain** | Composition of blocks in processing order - independent of shootouts |
| **Shootout** | A/B tone comparison using signal chains |

## Core Entities

### User Management

| Entity | Description |
|--------|-------------|
| User | User account |
| UserIdentity | OAuth provider link (multi-provider per user) |
| OAuthProvider | OAuth provider configuration |

### Unified Gear Model

| Entity | Description |
|--------|-------------|
| Gear | Equipment item (unified across all sources) |
| GearModel | Specific model file (NAM, IR, etc.) within gear |
| GearSource | Source attribution (t3k, community, etc.) |
| GearTag | Categorisation tags |
| GearMake | Manufacturer/brand |
| UserGear | User's gear library (references Gear) |

### Signal Chains

| Entity | Description |
|--------|-------------|
| SignalChain | Aggregate root - composition of blocks |
| SignalChainBlock | Single block in chain (gear OR built-in processor) |
| SignalChainGroup | Collection of chains for permutation output |
| SignalChainGroupAmp | Amp selections for group permutation |
| SignalChainGroupIR | IR selections for group permutation |
| BlockType | Built-in processor template (EQ, compressor, etc.) |
| Preset | Parameter values for a signal chain |

### Audio & Shootouts

| Entity | Description |
|--------|-------------|
| DITrack | User-uploaded guitar recording |
| Shootout | A/B comparison configuration |
| ShootoutChain | Signal chain reference within a shootout |

### System

| Entity | Description |
|--------|-------------|
| Job | Background job tracking |
| ErrorReport | Error tracking |
| UserNotification | User notifications |
| Audit | Audit trail |

## Gear Types

| Type | Description |
|------|-------------|
| AMP | Amplifier model (HEAD - requires IR) |
| FULL_RIG | Complete amp + cab combination (IR baked in) |
| PEDAL | Effects pedal |
| OUTBOARD | Rack/outboard gear |
| IR | Impulse response (cabinet simulation) |

## Gear Platforms

| Platform | Description |
|----------|-------------|
| NAM | Neural Amp Modeler |
| IR | Impulse Response |
| AIDA_X | AIDA-X format |
| AA_SNAPSHOT | Atomic Amplifire snapshot |
| PROTEUS | Proteus format |

## Signal Chain Blocks

A block is a single component in a signal chain. Can contain:

**Gear-based blocks:**
- Amp (exactly one required per chain)
- IR (optional, zero or one)
- Pedal (zero or more, positioned pre-amp, loop, or post)

**Built-in processor blocks (BlockType):**

| Category | Types |
|----------|-------|
| Utility | Noise Gate, Gain |
| EQ | Parametric EQ, Graphic EQ |
| Dynamics | Compressor, Limiter |
| Filter | High-pass, Low-pass |
| Delay | Delay |
| Reverb | Reverb |
| Modulation | Chorus, Flanger, Phaser |

## Signal Chain Grammar

```
DI Track -> [Pre-Effects*] -> Amp -> [Loop Effects*] -> [IR?] -> [Post-Effects*] -> Output
                                        ^
                              (not allowed if FULL_RIG)
```

| Position | Allowed | Description |
|----------|---------|-------------|
| Pre-Effects | Pedals, built-in processors | Before amp (overdrive, boost, wah, compressor) |
| Amp | Exactly one | HEAD (requires IR) or FULL_RIG (forbids IR) |
| Loop Effects | Pedals, built-in processors | Between amp and cabinet (EQ, modulation); **not allowed with FULL_RIG** |
| IR | Zero or one | Cabinet simulation; required for HEAD, forbidden for FULL_RIG |
| Post-Effects | Pedals, built-in processors | After cabinet (delay, reverb, spatial) |

**Validation Rules:**

| Error | Condition |
|-------|-----------|
| NO_AMP | No amp block in chain |
| MULTIPLE_AMPS | More than one amp block |
| IR_REQUIRED | HEAD amp but no IR provided |
| IR_FORBIDDEN | FULL_RIG amp but IR provided |
| MULTIPLE_IRS | More than one IR block |
| LOOP_FORBIDDEN | Loop effects present with FULL_RIG amp |
| INVALID_ORDER | Blocks in wrong position |

## User-Uploaded IRs

User-uploaded IRs use the **unified Gear model** (same as source IRs):
- `IRUploadService` creates Gear + GearModel in one operation
- Source is "community" (not a data source adapter)
- 1:1 ratio (each uploaded IR is separate gear item)
- Accessible via UserGear -> GearModel -> Gear chain

## Value Objects

| Value Object | Description |
|--------------|-------------|
| GearType | Enum of gear types |
| Platform | Enum of model platforms |
| AudioChecksum | SHA256 hash of audio file |
| WaveformData | Visualisation data for audio |
| BlockCategory | Enum of block categories |
| BlockPosition | Enum of positions in signal chain (pre, loop, post) |

## Aggregate Identity

Each aggregate instance in the sync pipeline is owned by exactly one source. Aggregate identity is source-scoped.

**Composite key:** `(source_name, source_record_id)`

Core persists source identity for traceability and audit. Cross-source merging is **not performed in the ingestion pipeline**. If multiple sources describe the same real-world entity (e.g., two sources both provide data about "Fender Twin Reverb"), they are treated as separate aggregate instances. Entity resolution, if required, is a downstream concern handled by read models.
