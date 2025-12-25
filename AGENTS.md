# Guitar Tone Shootout - Development Operations Guide

**Version:** 1.0 | **Last Updated:** 2025-12-25

This document defines the development workflow, patterns, and automation for the Guitar Tone Shootout project. It serves as the primary reference for both human developers and AI agents.

---

## Quick Reference

```bash
# Development Workflow
gh issue create --title "feat: <description>"    # Create issue
git checkout -b <issue-number>-<short-desc>      # Create branch
# ... implement ...
just check                                        # Run all quality gates
gh pr create                                      # Create PR

# Quality Gates
just check              # All checks (lint, format, type, test)
just lint               # Ruff linting
just format             # Ruff formatting
just check-pipeline     # Pipeline checks only
just check-web          # Web checks only

# Task Management
just new-issue          # Create GitHub issue interactively
just pr                 # Create PR from current branch
```

---

## Workflow Phases

### Phase 0: Issue Creation

Every feature, bug fix, or task starts with a GitHub issue.

```bash
# Create a feature issue
gh issue create --title "feat: implement CLI commands" \
  --body "## Description
Implement Click-based CLI for processing comparisons.

## Acceptance Criteria
- [ ] \`shootout process <ini>\` processes a comparison
- [ ] \`shootout validate <ini>\` validates config
- [ ] Error handling with helpful messages

## Technical Notes
- Use Click library
- Follow existing patterns in config.py"
```

**Issue Title Conventions:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Test additions/fixes
- `chore:` - Maintenance tasks

### Phase 1: Branch Creation

```bash
# Get issue number (e.g., 42)
git checkout main
git pull origin main
git checkout -b 42-cli-commands
```

**Branch Naming:** `<issue-number>-<short-description>`

### Phase 2: Development

1. **Create dev-doc** for complex tasks (optional for simple fixes):
   ```bash
   mkdir -p dev/active
   touch dev/active/42-cli-commands.md
   ```

2. **Implement** following the patterns in this document

3. **Run quality gates** frequently:
   ```bash
   just check
   ```

### Phase 3: Quality Gates

All must pass before PR:

| Check | Command | What it does |
|-------|---------|--------------|
| Lint | `just lint` | Ruff linting with auto-fix |
| Format | `just format` | Ruff formatting |
| Types | `cd pipeline && just typecheck` | mypy strict mode |
| Tests | `cd pipeline && just test` | pytest |

### Phase 4: Pull Request

```bash
# Push branch
git push -u origin $(git branch --show-current)

# Create PR
gh pr create --title "feat: implement CLI commands" --body "$(cat <<'EOF'
## Summary
- Implemented Click-based CLI for comparison processing
- Added validation command

## Changes
- Added `cli.py` with process and validate commands
- Updated `__init__.py` with CLI entry point

## Related Issues
Closes #42

## Test Plan
- [ ] `just check` passes
- [ ] Manual test with sample INI file

---
Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Phase 5: Merge

After PR approval:
```bash
gh pr merge --squash
git checkout main
git pull origin main
git branch -d 42-cli-commands
```

Move dev-doc to archive (if created):
```bash
mv dev/active/42-cli-commands.md dev/archive/
```

---

## Project Structure

```
guitar-tone-shootout/
├── pipeline/                   # Audio/video processing (Python)
│   ├── src/guitar_tone_shootout/
│   │   ├── audio.py           # NAM + Pedalboard processing
│   │   ├── cli.py             # Click CLI
│   │   ├── config.py          # INI parsing
│   │   └── pipeline.py        # FFmpeg + Playwright
│   ├── tests/
│   └── pyproject.toml
├── web/                        # Web frontend (Flask + HTMX)
│   ├── app/                   # Flask application
│   ├── templates/             # Jinja2 templates
│   ├── static/src/            # Source CSS/JS
│   ├── static/dist/           # Built assets
│   └── pyproject.toml
├── dev/                        # Development docs
│   ├── active/                # Current work
│   ├── archive/               # Completed work
│   └── roadmap.md             # Project roadmap
├── .claude/                    # Claude Code configuration
│   ├── settings.json          # Permissions and settings
│   └── skills/                # Specialized prompts
├── .github/                    # GitHub configuration
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── inputs/                     # DI tracks, NAM models, IRs
├── outputs/                    # Generated audio/video
├── comparisons/                # INI config files
├── templates/                  # HTML templates for images
├── AGENTS.md                   # This file
└── CLAUDE.md                   # Pointer to AGENTS.md
```

---

## Code Patterns

### Python Style

```python
# Type hints required on all functions
def process_audio(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 44100,
) -> None:
    """Process audio through signal chain.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        sample_rate: Target sample rate

    Raises:
        FileNotFoundError: If input file doesn't exist
        AudioProcessingError: If processing fails
    """
    ...
```

**Rules:**
- Type hints on all functions
- Docstrings for public functions
- No `print()` - use `logging` module
- `pathlib.Path` over string paths
- Specific exceptions, not bare `except:`
- Lazy imports for heavy dependencies (torch, playwright)

### Testing Pattern

```python
# tests/test_config.py
import pytest
from guitar_tone_shootout.config import parse_comparison

class TestParseComparison:
    """Tests for parse_comparison function."""

    def test_valid_config(self, tmp_path: Path) -> None:
        """Should parse valid INI config."""
        config_path = tmp_path / "test.ini"
        config_path.write_text(VALID_CONFIG)

        result = parse_comparison(config_path)

        assert result.meta.name == "Test Comparison"

    def test_missing_section_raises(self, tmp_path: Path) -> None:
        """Should raise ConfigError for missing required section."""
        config_path = tmp_path / "test.ini"
        config_path.write_text(INVALID_CONFIG)

        with pytest.raises(ConfigError, match="Missing required section"):
            parse_comparison(config_path)
```

### Error Handling Pattern

```python
# Custom exceptions in exceptions.py
class ShootoutError(Exception):
    """Base exception for all shootout errors."""

class ConfigError(ShootoutError):
    """Configuration file error."""

class AudioProcessingError(ShootoutError):
    """Audio processing error."""

class PipelineError(ShootoutError):
    """Pipeline execution error."""

# Usage
def load_nam_model(path: Path) -> NAMModel:
    if not path.exists():
        raise AudioProcessingError(f"NAM model not found: {path}")
    try:
        return _load_model(path)
    except Exception as e:
        raise AudioProcessingError(f"Failed to load NAM model: {e}") from e
```

---

## Subproject Patterns

### Pipeline (`pipeline/`)

The audio/video processing engine.

**Key modules:**
- `config.py` - INI parsing with dataclasses
- `audio.py` - NAM + Pedalboard processing
- `pipeline.py` - FFmpeg + Playwright orchestration
- `cli.py` - Click-based CLI

**Dependencies:** torch, nam, pedalboard, playwright, jinja2

### Web (`web/`)

The Flask + HTMX web interface (future phase).

**Key patterns:**
- Server-side rendering with Jinja2
- HTMX for dynamic updates
- Tailwind CSS 4 for styling
- Flowbite components

**Dependencies:** flask, htmx (via CDN), tailwindcss, flowbite

---

## External Dependencies

| Tool | Purpose | Installation |
|------|---------|--------------|
| FFmpeg | Video/audio processing | `brew install ffmpeg` |
| uv | Python package management | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| just | Task runner | `cargo install just` |
| pnpm | Node package manager | `npm install -g pnpm` |
| prek | Git hooks (Rust-based) | `uv tool install prek` |
| Playwright | Browser automation | `playwright install chromium` |

---

## Claude Code Integration

### Autonomous Execution

The following commands are pre-approved for immediate execution:

```bash
# Quality gates
just check
just lint
just format
cd pipeline && just test
cd pipeline && just typecheck

# Git operations (read-only)
git status
git log
git diff
git branch

# GitHub CLI (read-only)
gh issue list
gh pr list
gh pr view
```

### Skills

Located in `.claude/skills/`:

- **pipeline-dev**: Audio processing, NAM models, Pedalboard effects
- **web-dev**: Flask, HTMX, Tailwind, Flowbite patterns
- **testing**: pytest patterns, fixture usage

### Hooks

Located in `.claude/hooks/`:

- **pre-commit**: Runs quality gates before git commit
- **post-edit**: Suggests running tests after file modifications

---

## Troubleshooting

### Common Issues

**NAM model fails to load:**
- Ensure `.nam` file is valid JSON
- Check PyTorch version compatibility
- Verify CUDA availability (if using GPU)

**Playwright fails:**
- Run `playwright install chromium`
- Check browser version compatibility

**FFmpeg encoding fails:**
- Verify input file format
- Check output directory permissions
- Review FFmpeg error output

### Getting Help

1. Check existing issues: `gh issue list`
2. Search codebase: `just grep <pattern>` (if implemented)
3. Ask in discussions: `gh discussion create`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-25 | Initial workflow documentation |
