#!/usr/bin/env bash
# first-time-setup.sh - Guitar Tone Shootout First-Time Setup
#
# Usage:
#   ./scripts/first-time-setup.sh              # Run from repo
#
# This script bootstraps the development environment:
#   1. Installs tier-0 prereqs (just, uv, Python)
#   2. Converts to worktree structure if needed
#   3. Runs `just infra` to install remaining prereqs
#   4. Runs `./worktree.py setup main` to start services
#
# Tier-0 prereqs (installed by this script):
#   - just (task runner) - via cargo/brew/apt
#   - uv (Python package manager) - via curl
#   - Python 3.12 - via uv
#
# Tier-1 prereqs (installed by `just infra`):
#   - Python deps for worktree CLI and E2E tests
#   - Playwright browser
#   - System dependencies (prompted)

set -euo pipefail

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${BLUE}==>${NC} ${BOLD}$1${NC}"; }

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == darwin* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == linux* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}  Guitar Tone Shootout - First Time Setup${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""

# ============================================
# Step 1: Install Tier-0 Prerequisites
# ============================================
log_step "Checking tier-0 prerequisites..."

# --- just (task runner) ---
if command -v just &> /dev/null; then
    JUST_VERSION=$(just --version | cut -d' ' -f2)
    log_info "just: $JUST_VERSION"
else
    log_warn "just not found - installing..."
    echo ""

    # Prefer cargo (just is written in Rust)
    if command -v cargo &> /dev/null; then
        read -p "Install just via cargo? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            cargo install just
            log_info "just installed via cargo"
        else
            log_error "just is required. Install manually: https://github.com/casey/just#installation"
            exit 1
        fi
    elif command -v brew &> /dev/null; then
        read -p "Install just via brew? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            brew install just
            log_info "just installed via brew"
        else
            log_error "just is required. Install manually: https://github.com/casey/just#installation"
            exit 1
        fi
    elif command -v apt &> /dev/null; then
        read -p "Install just via apt? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo apt update && sudo apt install -y just
            log_info "just installed via apt"
        else
            log_error "just is required. Install manually: https://github.com/casey/just#installation"
            exit 1
        fi
    elif command -v pacman &> /dev/null; then
        read -p "Install just via pacman? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo pacman -S just
            log_info "just installed via pacman"
        else
            log_error "just is required. Install manually: https://github.com/casey/just#installation"
            exit 1
        fi
    else
        log_error "No package manager found (cargo/brew/apt/pacman)"
        echo ""
        echo "Install cargo (recommended): https://rustup.rs"
        echo "Then run: cargo install just"
        echo ""
        echo "Or see: https://github.com/casey/just#installation"
        exit 1
    fi
fi

# --- uv (Python package manager) ---
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version | cut -d' ' -f2)
    log_info "uv: $UV_VERSION"
else
    log_warn "uv not found - installing..."
    echo ""
    read -p "Install uv via official installer? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Source the env to get uv in PATH for this session
        if [[ -f "$HOME/.local/bin/env" ]]; then
            source "$HOME/.local/bin/env"
        elif [[ -f "$HOME/.cargo/env" ]]; then
            source "$HOME/.cargo/env"
        fi

        # Verify installation
        if command -v uv &> /dev/null; then
            log_info "uv installed"
        else
            log_error "uv installed but not in PATH"
            echo ""
            echo "Add to your shell config:"
            echo '  export PATH="$HOME/.local/bin:$PATH"'
            echo ""
            echo "Then restart your shell and re-run this script."
            exit 1
        fi
    else
        log_error "uv is required. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

# --- Python 3.12 (via uv) ---
# Check if Python 3.12+ is available via uv
if uv python find 3.12 &> /dev/null; then
    PYTHON_VERSION=$(uv python find 3.12)
    log_info "Python 3.12: $PYTHON_VERSION"
else
    log_warn "Python 3.12 not found - installing via uv..."
    uv python install 3.12
    log_info "Python 3.12 installed"
fi

# ============================================
# Step 2: Check Other Prerequisites (fail-fast)
# ============================================
log_step "Checking system prerequisites..."

MISSING_PREREQS=()

# Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    log_info "Docker: $DOCKER_VERSION"
else
    log_error "Docker not found"
    MISSING_PREREQS+=("docker")
fi

# Docker Compose (v2)
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version --short)
    log_info "Docker Compose: $COMPOSE_VERSION"
else
    log_error "Docker Compose (v2) not found"
    MISSING_PREREQS+=("docker-compose-v2")
fi

# Docker daemon running
if command -v docker &> /dev/null && ! docker info &> /dev/null 2>&1; then
    log_error "Docker daemon not running"
    echo ""
    echo "Start Docker Desktop or the Docker daemon:"
    if [[ "$OS" == "macos" ]]; then
        echo "  open -a Docker"
    elif [[ "$OS" == "linux" ]]; then
        echo "  sudo systemctl start docker"
    fi
    exit 1
fi

# Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    log_info "Git: $GIT_VERSION"
else
    log_error "Git not found"
    MISSING_PREREQS+=("git")
fi

# gh CLI
if command -v gh &> /dev/null; then
    GH_VERSION=$(gh --version | head -1 | cut -d' ' -f3)
    log_info "gh CLI: $GH_VERSION"
else
    log_error "gh CLI not found (required for GitHub workflow)"
    MISSING_PREREQS+=("gh")
fi

# Exit if missing prerequisites
if [ ${#MISSING_PREREQS[@]} -gt 0 ]; then
    echo ""
    log_error "Missing prerequisites: ${MISSING_PREREQS[*]}"
    echo ""
    echo "Install missing tools:"
    if [[ "$OS" == "macos" ]]; then
        echo "  brew install ${MISSING_PREREQS[*]}"
    elif [[ "$OS" == "linux" ]]; then
        if command -v apt &> /dev/null; then
            echo "  sudo apt install ${MISSING_PREREQS[*]}"
        elif command -v pacman &> /dev/null; then
            echo "  sudo pacman -S ${MISSING_PREREQS[*]}"
        fi
    fi
    exit 1
fi

# ============================================
# Step 3: Check Repository Structure
# ============================================
log_step "Checking repository structure..."

# Determine where we are
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    REPO_DIR="$(dirname "$SCRIPT_DIR")"
else
    REPO_DIR="$(pwd)"
fi

# Must be inside the GTS repository (the main checkout). The bare-repo + main
# layout is already established; there is no longer a conversion step.
if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_error "Not in a Guitar Tone Shootout repository"
    echo ""
    echo "Clone the repository first:"
    echo "  git clone https://github.com/krazyuniks/guitar-tone-shootout.git"
    echo "  cd guitar-tone-shootout"
    echo "  ./scripts/first-time-setup.sh"
    exit 1
fi

cd "$REPO_DIR"

# ============================================
# Step 4: host development dependencies (prek, Playwright, etc.)
# ============================================
log_step "Installing development dependencies..."
just infra

# ============================================
# Step 5: ensure secrets, then bring up the main dev stack
# ============================================
# Mint env.local.sh on first run (the engine seeds feature worktrees per-run,
# but the long-running main stack reads env.local.sh directly). Existing values
# are never overwritten.
if [[ ! -f env.local.sh ]]; then
    log_step "Generating env.local.sh (gitignored secrets)..."
    cat > env.local.sh <<EOF
export DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
export OAUTH_ENCRYPTION_KEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export GTS_ADMIN_PASSWORD=""
export T3K_API_KEY=""
EOF
    chmod 600 env.local.sh
fi

log_step "Starting the main stack..."
just up-d

# ============================================
# Success!
# ============================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "  ${BOLD}Open the app:${NC}  http://localhost:9000"
echo ""
echo -e "  ${BOLD}Quick commands:${NC}"
echo "    just up-d             Start the main stack"
echo "    just watch-astro      Auto-rebuild templates"
echo "    just check            Run all quality checks (in a feature worktree)"
echo "    just tdd <test>       Run a specific test"
echo "    just logs             View service logs"
echo ""
echo -e "  ${BOLD}Working on a feature (engine-driven):${NC}"
echo "    worktree up gts <branch>    Create + provision a feature worktree"
echo "    worktree gate gts <branch>  Run the gate in it"
echo "    worktree down gts <branch>  Tear it down"
echo ""
fi
