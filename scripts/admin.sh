#!/bin/bash
# Admin script for Guitar Tone Shootout
# Similar to rust project worktree.sh for common maintenance tasks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Update all dependencies to latest versions
cmd_update_deps() {
    log_info "Updating all dependencies to latest versions..."

    # Frontend (npm packages)
    log_info "Updating frontend npm packages..."
    cd "$PROJECT_ROOT/frontend"
    if command -v ncu &> /dev/null; then
        ncu -u
        pnpm install
        log_success "Frontend packages updated"
    else
        log_warn "npm-check-updates not installed. Run: npm install -g npm-check-updates"
    fi

    # Backend (Python packages)
    log_info "Updating backend Python packages..."
    cd "$PROJECT_ROOT/backend"
    if command -v uv &> /dev/null; then
        # Update pyproject.toml dependencies to latest
        log_info "Check https://pypi.org for latest versions and update pyproject.toml manually"
        log_info "Then run: docker compose build backend"
    fi

    cd "$PROJECT_ROOT"
    log_success "Dependency update complete"
}

# Check for outdated dependencies
cmd_check_deps() {
    log_info "Checking for outdated dependencies..."

    # Frontend
    log_info "Frontend packages:"
    cd "$PROJECT_ROOT/frontend"
    if command -v ncu &> /dev/null; then
        ncu
    else
        pnpm outdated || true
    fi

    cd "$PROJECT_ROOT"
}

# Update Docker base images to latest
cmd_update_docker() {
    log_info "Pulling latest Docker base images..."

    docker pull python:3.14-slim
    docker pull node:24-alpine
    docker pull postgres:16-alpine
    docker pull redis:7-alpine
    docker pull nginx:alpine

    log_success "Docker images updated"
    log_info "Rebuild containers with: docker compose build"
}

# Full rebuild of all containers
cmd_rebuild() {
    log_info "Rebuilding all Docker containers..."
    cd "$PROJECT_ROOT"
    docker compose build --no-cache
    log_success "Rebuild complete"
}

# Clean up Docker resources
cmd_clean() {
    log_info "Cleaning up Docker resources..."
    cd "$PROJECT_ROOT"
    docker compose down -v --remove-orphans
    docker system prune -f
    log_success "Cleanup complete"
}

# Show current versions
cmd_versions() {
    log_info "Current versions:"
    echo ""

    echo "Docker images:"
    docker compose config --images 2>/dev/null | while read img; do
        echo "  - $img"
    done
    echo ""

    echo "Backend (Python):"
    docker compose exec -T backend python --version 2>/dev/null || echo "  (container not running)"
    echo ""

    echo "Frontend (Node):"
    docker compose exec -T frontend node --version 2>/dev/null || echo "  (container not running)"
    echo ""

    echo "Database:"
    docker compose exec -T db psql --version 2>/dev/null || echo "  (container not running)"
}

# Run all quality checks
cmd_check() {
    log_info "Running quality checks..."
    cd "$PROJECT_ROOT"

    log_info "Backend checks..."
    docker compose exec -T backend ruff check . || true
    docker compose exec -T backend ruff format --check . || true

    log_info "Frontend checks..."
    docker compose exec -T frontend pnpm check || true

    log_success "Quality checks complete"
}

# Show help
cmd_help() {
    echo "Guitar Tone Shootout Admin Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  update-deps    Update all dependencies to latest versions"
    echo "  check-deps     Check for outdated dependencies"
    echo "  update-docker  Pull latest Docker base images"
    echo "  rebuild        Full rebuild of all containers (no cache)"
    echo "  clean          Clean up Docker resources and volumes"
    echo "  versions       Show current versions of all components"
    echo "  check          Run all quality checks"
    echo "  help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 update-deps     # Update npm and Python packages"
    echo "  $0 rebuild         # Rebuild after dependency updates"
}

# Main
case "${1:-help}" in
    update-deps)    cmd_update_deps ;;
    check-deps)     cmd_check_deps ;;
    update-docker)  cmd_update_docker ;;
    rebuild)        cmd_rebuild ;;
    clean)          cmd_clean ;;
    versions)       cmd_versions ;;
    check)          cmd_check ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
