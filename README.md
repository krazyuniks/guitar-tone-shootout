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

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Core language |
| uv | Latest | Python package manager |
| just | Latest | Task runner |
| FFmpeg | 6.0+ | Audio/video processing |
| Node.js | 20+ | Web frontend build tools (optional for MVP) |
| pnpm | 9+ | Node package manager (optional for MVP) |

### Installation by Platform

<details>
<summary><strong>macOS</strong></summary>

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.12 ffmpeg just

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js and pnpm (for web frontend - optional for MVP)
brew install node
npm install -g pnpm
```
</details>

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# Update package list
sudo apt update

# Install Python 3.12
sudo apt install python3.12 python3.12-venv

# Install FFmpeg
sudo apt install ffmpeg

# Install just
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js 20+ and pnpm (for web frontend - optional for MVP)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs
npm install -g pnpm

# Add ~/.local/bin to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```
</details>

<details>
<summary><strong>Windows</strong></summary>

**Option 1: Using winget (Windows 11 / Windows 10 21H2+)**
```powershell
# Install dependencies
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install Casey.Just
winget install OpenJS.NodeJS.LTS

# Install uv (run in PowerShell as Administrator)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install pnpm
npm install -g pnpm
```

**Option 2: Using Scoop**
```powershell
# Install Scoop if not present
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex

# Install dependencies
scoop install python ffmpeg just nodejs

# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install pnpm
npm install -g pnpm
```

**Option 3: Manual installation**
- Python 3.12+: https://www.python.org/downloads/
- FFmpeg: https://ffmpeg.org/download.html (add to PATH)
- just: https://github.com/casey/just/releases
- Node.js 20+: https://nodejs.org/
- uv: `pip install uv` (after Python is installed)
- pnpm: `npm install -g pnpm` (after Node.js is installed)
</details>

### Verify Installation

```bash
python3 --version    # Should be 3.12+
uv --version         # Should show version
just --version       # Should show version
ffmpeg -version      # Should show version 6+
node --version       # Should be 20+ (optional for MVP)
pnpm --version       # Should be 9+ (optional for MVP)
```

### Setup

```bash
git clone https://github.com/krazyuniks/guitar-tone-shootout.git
cd guitar-tone-shootout
just setup
```

### Install Playwright Browser (Required for Image Generation)

```bash
cd pipeline
uv run playwright install chromium
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

Outputs will be in `outputs/<shootout-title>/`:
- `<shootout-title>.mp4` - Final comparison video (YouTube-ready)
- `audio/<shootout-title>_NNN.flac` - Per-segment FLAC files
- `audio/<shootout-title>_full.flac` - Combined full audio (for SoundCloud etc.)
- `clips/<shootout-title>_NNN.mp4` - Individual video clips per segment
- `images/<shootout-title>_NNN.png` - Generated segment images

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
├── outputs/            # Generated files (per shootout)
│   └── <shootout-title>/   # One folder per comparison
│       ├── <shootout-title>.mp4  # Final comparison video
│       ├── audio/          # FLAC files (_NNN.flac, _full.flac)
│       ├── images/         # Segment images (_NNN.png)
│       └── clips/          # Individual video clips (_NNN.mp4)
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

## Testing

The test suite is organized into three categories with increasing scope and dependencies:

### Test Categories

| Category | Command | Speed | Dependencies |
|----------|---------|-------|--------------|
| **Unit** | `just test-unit` | Fast (~4s) | Python only |
| **Integration** | `just test-integration` | Medium (~10s) | FFmpeg, Pillow |
| **E2E** | `just test-e2e` | Slow (~30s) | FFmpeg, Playwright |

### Running Tests

```bash
cd pipeline

# Run all tests
just test

# Run only fast unit tests (mocked dependencies)
just test-unit

# Run integration tests (requires FFmpeg)
just test-integration

# Run end-to-end tests (requires FFmpeg + Playwright)
just test-e2e

# Run tests with coverage report
just test-cov

# Generate test fixtures (if missing)
just generate-fixtures
```

### Test Structure

```
pipeline/tests/
├── conftest.py              # Shared fixtures & pytest config
├── fixtures/                # Test data files
│   ├── di_tracks/           # Test DI audio files
│   ├── irs/                 # Test impulse responses
│   ├── nam_models/          # Test NAM models (if any)
│   ├── comparisons/         # Test INI files
│   └── generate_fixtures.py # Script to regenerate fixtures
├── unit/                    # Fast tests with mocked dependencies
│   ├── test_audio.py
│   ├── test_config.py
│   └── test_pipeline.py
├── integration/             # Tests with real FFmpeg/files
│   ├── test_audio_processing.py
│   └── test_pipeline_processing.py
└── e2e/                     # Full workflow tests
    └── test_comparison_workflow.py
```

### Writing Tests

Tests are auto-marked based on their location:
- `tests/unit/` → `@pytest.mark.unit`
- `tests/integration/` → `@pytest.mark.integration`
- `tests/e2e/` → `@pytest.mark.e2e`

Use fixtures from `conftest.py`:

```python
def test_my_feature(test_di_track: Path, sample_audio: np.ndarray) -> None:
    """Example test using fixtures."""
    # test_di_track: Path to test DI WAV file
    # sample_audio: 1 second of 440Hz sine wave
    ...
```

## Resources

- [NAM Models on Tone3000](https://tone3000.com)
- [Pedalboard Documentation](https://spotify.github.io/pedalboard/)
- [Neural Amp Modeler](https://github.com/sdatkinson/neural-amp-modeler)

## License

MIT

## Contributing

We welcome contributions! This project uses an issue-driven development workflow.

### Development Workflow

1. **Create an issue** for your feature/fix:
   ```bash
   gh issue create --title "feat: your feature description"
   ```
   Or use the [issue templates](https://github.com/krazyuniks/guitar-tone-shootout/issues/new/choose)

2. **Create a branch** from the issue:
   ```bash
   just branch 42   # Creates branch 42-feature
   ```

3. **Develop** following the patterns in `AGENTS.md`

4. **Run quality checks** before committing:
   ```bash
   just check       # Runs lint, format, typecheck, test
   ```

5. **Create a PR**:
   ```bash
   just pr          # Creates PR with template
   ```

### Quick Commands

```bash
just issues       # List open issues
just issue 42     # View issue details
just pr-status    # Check PR status
just ship "msg"   # Check + commit + push + PR
```

### Code Style

- Type hints required on all functions
- Docstrings for public functions
- Use `logging` instead of `print()`
- Use `pathlib.Path` over string paths
- See `AGENTS.md` for detailed patterns
