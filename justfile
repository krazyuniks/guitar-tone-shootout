# Guitar Tone Shootout - Root Task Runner
# Orchestrates subprojects: pipeline/ and web/

default:
    @just --list

# ============================================
# Setup
# ============================================

# Setup all subprojects
setup: setup-pipeline setup-web install-hooks
    @echo "✓ All subprojects setup complete"

# Setup pipeline subproject
setup-pipeline:
    cd pipeline && just setup

# Setup web subproject
setup-web:
    cd web && just setup

# ============================================
# Code Quality (All Subprojects)
# ============================================

# Run all checks across all subprojects
check: check-pipeline check-web
    @echo "✓ All checks passed"

# Check pipeline subproject
check-pipeline:
    cd pipeline && just check

# Check web subproject
check-web:
    cd web && just check

# Lint all subprojects
lint:
    cd pipeline && just lint
    cd web && just lint

# Format all subprojects
format:
    cd pipeline && just format
    cd web && just format

# ============================================
# Pipeline Tasks
# ============================================

# Process a comparison INI file
process ini_file:
    cd pipeline && just process ../{{ini_file}}

# Validate a comparison INI file
validate ini_file:
    cd pipeline && just validate ../{{ini_file}}

# ============================================
# Web Tasks
# ============================================

# Run web development server
serve:
    cd web && just serve-dev

# Build web frontend assets
build-web:
    cd web && just build

# ============================================
# Shared Directories
# ============================================

# Clean output directories
clean-outputs:
    rm -rf outputs/audio/*
    rm -rf outputs/images/*
    rm -rf outputs/clips/*
    rm -rf outputs/videos/*
    @echo "✓ Outputs cleaned"

# Create a new comparison from template
new-comparison name:
    cp comparisons/example.ini "comparisons/{{name}}.ini"
    @echo "✓ Created comparisons/{{name}}.ini"

# ============================================
# Environment Checks
# ============================================

# Check all external dependencies
check-deps:
    @echo "Checking dependencies..."
    @which ffmpeg > /dev/null && echo "✓ FFmpeg: $(ffmpeg -version 2>&1 | head -1)" || echo "✗ FFmpeg not found"
    @which tailwindcss > /dev/null && echo "✓ Tailwind CSS: $(tailwindcss --help 2>&1 | head -1)" || echo "✗ Tailwind CSS not found (run: cd web && just install-tools)"
    @which esbuild > /dev/null && echo "✓ esbuild: $(esbuild --version)" || echo "✗ esbuild not found (run: cd web && just install-tools)"
    @which uv > /dev/null && echo "✓ uv: $(uv --version)" || echo "✗ uv not found"
    @which just > /dev/null && echo "✓ just: $(just --version)" || echo "✗ just not found"
    @which prek > /dev/null && echo "✓ prek: $(prek --version)" || echo "✗ prek not found (run: uv tool install prek)"
    @python3 --version 2>/dev/null || echo "✗ Python 3 not found"

# ============================================
# Git Hooks (prek - Rust-based, faster than pre-commit)
# ============================================

# Install prek hooks
install-hooks:
    prek install
    @echo "✓ prek hooks installed"

# Run prek hooks on all files
run-hooks:
    prek run --all-files

# Uninstall prek hooks
uninstall-hooks:
    prek uninstall
    @echo "✓ prek hooks uninstalled"

# ============================================
# Clean
# ============================================

# Clean all generated files
clean-all: clean-outputs
    rm -rf pipeline/.venv pipeline/.pytest_cache pipeline/.mypy_cache pipeline/.ruff_cache
    rm -rf web/.venv web/.pytest_cache web/.mypy_cache web/.ruff_cache
    rm -rf web/static/dist/*.css web/static/dist/*.js web/node_modules
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    @echo "✓ All generated files cleaned"

# ============================================
# GitHub Workflow
# ============================================

# Create a new feature issue
new-issue:
    @echo "Creating new issue..."
    @echo "Use: gh issue create --title 'feat: <description>'"
    @echo "Or go to: https://github.com/krazyuniks/guitar-tone-shootout/issues/new/choose"
    gh issue list --limit 5

# Create a feature branch from issue number
branch issue:
    git checkout main
    git pull origin main
    git checkout -b {{issue}}-feature
    @echo "✓ Created branch {{issue}}-feature"
    @echo "Remember to create dev doc: touch dev/active/{{issue}}-feature.md"

# Create a PR for current branch
pr:
    @echo "Creating PR..."
    gh pr create --fill

# View current PR status
pr-status:
    gh pr status

# List open issues
issues:
    gh issue list

# View issue details
issue num:
    gh issue view {{num}}

# ============================================
# Development Workflow
# ============================================

# Quick check before commit
pre-commit: check
    @echo "✓ Ready to commit"

# Full workflow: check, commit, push, PR
ship message:
    just check
    git add -A
    git commit -m "{{message}}"
    git push -u origin $(git branch --show-current)
    gh pr create --fill
    @echo "✓ PR created!"
