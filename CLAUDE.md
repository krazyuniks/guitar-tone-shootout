# Guitar Tone Shootout

## Project Overview

A CLI-driven pipeline for creating guitar amp/cab comparison videos for YouTube. Processes DI (direct input) guitar tracks through Neural Amp Modeler (NAM) captures and impulse responses (IRs), generates comparison images, and outputs YouTube-ready videos.

## Tech Stack

- **Python 3.12+** - Core language
- **uv** - Package and environment management (Rust-based)
- **Pedalboard** - Audio processing (Spotify's VST host library)
- **FFmpeg** - Video generation, audio concatenation, silence trimming
- **Puppeteer/Playwright** - HTML/CSS to image rendering
- **Ruff** - Linting and formatting (Rust-based)
- **mypy** - Static type checking
- **pre-commit** - Git hooks
- **just** - Task runner (Rust-based)

### Web Frontend (Future)

- **Flask** - Python web framework (server-side rendering)
- **HTMX** - Dynamic interactions without heavy JS
- **Tailwind CSS 4** - Styling (standalone CLI, Rust-based, no Node)
- **Flowbite** - Tailwind component library (vanilla JS)
- **esbuild** - JS bundling/minification (Go-based, no Node)

## Architecture

### Pipeline Flow

```
DI Track → Silence Trim → Pedalboard Processing → FLAC Audio
                              ↓
                    NAM Model + IR + Effects
                              ↓
              HTML/CSS → Image per permutation
                              ↓
              FFmpeg → Individual clips → Master video (MP4)
```

### Directory Structure

```
guitar-tone-shootout/
├── pipeline/                   # Audio/video processing subproject
│   ├── src/
│   │   └── guitar_tone_shootout/
│   │       ├── __init__.py
│   │       ├── cli.py          # Click-based CLI
│   │       ├── config.py       # INI parsing
│   │       └── pipeline.py     # Core processing
│   ├── tests/
│   ├── pyproject.toml          # Pipeline dependencies
│   └── justfile
├── web/                        # Web frontend subproject
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py             # Flask application
│   ├── templates/              # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   └── partials/
│   ├── static/
│   │   ├── src/                # Source CSS/JS
│   │   │   ├── styles.css
│   │   │   └── app.js
│   │   └── dist/               # Built assets
│   ├── tests/
│   ├── pyproject.toml          # Web dependencies
│   ├── tailwind.config.js
│   └── justfile
├── shared/                     # Shared models/config (future)
├── inputs/
│   ├── di_tracks/
│   ├── nam_models/
│   │   └── tone3000/{username}/{pack}/{capture}.nam
│   ├── irs/
│   │   └── {source}/{product}/{ir}.wav
│   └── other_captures/
├── comparisons/                # INI files (used by both subprojects)
│   └── {comparison_name}.ini
├── outputs/
│   ├── audio/                  # FLAC files
│   ├── images/                 # Generated images
│   ├── clips/                  # Intermediate clips
│   └── videos/                 # Final MP4s
├── templates/                  # HTML/CSS for image generation (pipeline)
├── CLAUDE.md
├── README.md
├── justfile                    # Root orchestration
└── .pre-commit-config.yaml
```

### Subproject Independence

Each subproject (`pipeline/` and `web/`) has:
- Its own `pyproject.toml` with isolated dependencies
- Its own `justfile` with subproject-specific tasks
- Its own `tests/` directory
- Independent virtual environments

This allows:
- Different testing frameworks per subproject
- Contributors to work on one without the other
- Cleaner dependency management
- Easier future extraction to separate repos

## Configuration Format (INI)

Each comparison is defined by an INI file in `comparisons/`:

```ini
[meta]
name = Marshall vs Fender Clean Comparison
guitar = Fender Stratocaster
pickup = bridge single coil
author = username

[di_tracks]
1 = clean_chord_progression.wav
2 = blues_lick.wav

[amps]
1 = tone3000/user1/marshall_pack/plexi_bright.nam
2 = tone3000/user2/fender_pack/twin_reverb_clean.nam

[cabs]
1 = ownhammer/412_greenback.wav
2 = ml_sound_lab/fender_2x12.wav
```

## Permutation Logic

- **Cabs outer loop, amps inner loop**
- Example with 2 amps, 2 cabs, 2 DI tracks = 8 segments
- Order: Cab1+Amp1+DI1, Cab1+Amp2+DI1, Cab1+Amp1+DI2, Cab1+Amp2+DI2, Cab2+Amp1+DI1...

## Output Specifications

### Audio (Standalone)
- Format: FLAC (lossless)
- Sample rate: Match input DI track
- Purpose: SoundCloud, other audio platforms

### Video (YouTube)
- Resolution: 1080p (1920x1080)
- Frame rate: 30fps
- Video codec: H.264
- Audio codec: AAC @ 384kbps stereo
- Sample rate: 48kHz
- Container: MP4

## Key Processing Steps

1. **Silence trimming**: FFmpeg `silenceremove` filter on DI tracks (automatic)
2. **Audio processing**: Pedalboard chains NAM model + IR + optional effects
3. **Image generation**: HTML/CSS template → Puppeteer screenshot per permutation
4. **Clip generation**: FFmpeg combines image + processed audio per permutation
5. **Master video**: FFmpeg concatenates all clips in INI-defined order
6. **Outputs**: FLAC audio + MP4 video saved separately

## External Resources

- **NAM Models**: https://tone3000.com (formerly ToneHunt)
- **Pedalboard Docs**: https://spotify.github.io/pedalboard/
- **FFmpeg Filters**: https://ffmpeg.org/ffmpeg-filters.html

## Development Commands

### Root (Orchestration)

```bash
just setup              # Setup all subprojects
just check              # Run checks on all subprojects
just lint               # Lint all subprojects
just format             # Format all subprojects
just process <ini>      # Process a comparison
just serve              # Run web dev server
just check-deps         # Verify external dependencies
```

### Pipeline Subproject

```bash
cd pipeline
just setup              # Create venv, install deps
just check              # Run all checks
just test               # Run pytest
just process <ini>      # Process comparison
```

### Web Subproject

```bash
cd web
just setup              # Create venv, install deps
just install-tools      # Install Tailwind CLI + esbuild
just build              # Build CSS + JS
just serve-dev          # Run Flask with auto-reload
just check              # Run all checks
```

## Future Enhancements

- Web UI for building comparisons (Flask + HTMX + Tailwind + Flowbite)
- Database-backed comparison storage
- Tone3000.com URL auto-download
- Docker containerization
- AWS pipeline automation
- Additional Pedalboard effects (EQ, compression, delay, reverb)
- Commercial VST support via Reaper fallback
- User authentication and profiles
- Job queue for async processing (Celery or RQ)

## Code Style

- Type hints required on all functions
- Docstrings for public functions
- No `print()` - use `logging` module
- Prefer `pathlib.Path` over string paths
- Error handling with specific exceptions
