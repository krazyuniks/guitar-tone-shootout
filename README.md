# Guitar Tone Shootout

A CLI pipeline for creating guitar amp/cab comparison videos for YouTube.

## What It Does

1. Takes DI (direct input) guitar recordings
2. Processes them through signal chains (NAM amp models, cabinet IRs, effects)
3. Generates professional comparison images showing the signal chain
4. Outputs YouTube-ready videos with all permutations

## Vocabulary

These terms are used consistently throughout the project:

| Term | Definition |
|------|------------|
| **Comparison** | A complete project comparing multiple signal chains across DI tracks. Defined by an INI file. |
| **DI Track** | A raw, unprocessed guitar recording (Direct Input) with associated metadata (guitar, pickup, notes). |
| **Signal Chain** | An ordered sequence of effects (amp, cab, pedals, etc.) that processes a DI track. |
| **Segment** | One processed audio/video clip representing 1 DI track × 1 signal chain. |
| **Permutation** | The full set of segments generated (all DI tracks × all signal chains). |
| **NAM** | Neural Amp Modeler - AI-based amp/pedal capture technology. Uses `.nam` model files. |
| **IR** | Impulse Response - Audio snapshot of a speaker cabinet's acoustic properties. Used for cab simulation. |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) - `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [just](https://github.com/casey/just) - `cargo install just`
- [FFmpeg](https://ffmpeg.org/) - `brew install ffmpeg` or download from ffmpeg.org

### Setup

```bash
git clone https://github.com/yourusername/guitar-tone-shootout.git
cd guitar-tone-shootout
just setup
```

### Usage

1. Add your DI tracks to `inputs/di_tracks/`
2. Add NAM models to `inputs/nam_models/`
3. Add cabinet IRs to `inputs/irs/`
4. Create a comparison INI file in `comparisons/`
5. Run the pipeline:

```bash
just process comparisons/my_comparison.ini
```

Outputs will be in:
- `outputs/audio/` - FLAC files (lossless, for SoundCloud etc.)
- `outputs/videos/` - MP4 files (YouTube-ready)

## Comparison INI Format

Each comparison is defined by an INI file with three sections:

```ini
[meta]
name = Marshall vs Fender Clean Comparison
author = your_username
description = Comparing classic American and British clean tones

[di_tracks]
# Each DI track has metadata
1.file = clean_chords.wav
1.guitar = Fender Stratocaster
1.pickup = bridge single coil
1.notes = recorded with fresh strings

2.file = blues_lick.wav
2.guitar = Gibson Les Paul
2.pickup = neck humbucker

[signal_chains]
# Each signal chain is a complete effects group
1.name = Plexi Crunch
1.description = Classic British crunch tone
1.chain = nam:marshall/plexi.nam, ir:greenback.wav

2.name = Twin Clean
2.description = Sparkling Fender clean
2.chain = nam:fender/twin.nam, ir:jensen.wav, reverb:hall
```

This generates 4 segments (2 DI tracks × 2 signal chains).

### Signal Chain Effect Types

| Type | Format | Description |
|------|--------|-------------|
| `nam` | `nam:<path>` | Neural Amp Modeler capture (.nam file) |
| `ir` | `ir:<path>` | Impulse Response / Cabinet sim (.wav file) |
| `eq` | `eq:<preset>` | EQ preset (highpass_80hz, lowpass_12k, etc.) |
| `reverb` | `reverb:<preset>` | Reverb preset (room, hall, plate, spring) |
| `delay` | `delay:<preset>` | Delay preset (slap, quarter, dotted_eighth) |
| `gain` | `gain:<value>` | Gain adjustment (e.g., +6db, -3db) |

## Output Specs

| Output | Format | Details |
|--------|--------|---------|
| Audio | FLAC | Lossless, original sample rate |
| Video | MP4 | 1080p, 30fps, H.264, AAC 384kbps |

## Project Structure

```
guitar-tone-shootout/
├── pipeline/           # Audio/video processing (Python)
│   ├── src/            # Source code
│   ├── tests/          # Pipeline tests
│   ├── pyproject.toml  # Dependencies
│   └── justfile        # Tasks
├── web/                # Web frontend (Flask + HTMX) - Future
├── inputs/             # Shared input files
│   ├── di_tracks/      # Raw guitar recordings
│   ├── nam_models/     # NAM amp/pedal captures
│   └── irs/            # Cabinet impulse responses
├── comparisons/        # INI comparison files
├── outputs/            # Generated files
│   ├── audio/          # FLAC files
│   ├── images/         # Segment images
│   ├── clips/          # Individual video clips
│   └── videos/         # Final comparison videos
└── justfile            # Root orchestration
```

## Development

### Quick Start

```bash
just setup      # Setup all subprojects
just check      # Run all checks (lint, format, types, tests)
```

### Pipeline Only

```bash
cd pipeline
just setup      # Install dependencies
just test       # Run tests
just check      # All checks
```

## Resources

- [NAM Models on Tone3000](https://tone3000.com)
- [Pedalboard Documentation](https://spotify.github.io/pedalboard/)
- [Neural Amp Modeler](https://github.com/sdatkinson/neural-amp-modeler)

## License

MIT

## Contributing

Contributions welcome! Please run `just check` before submitting PRs.
