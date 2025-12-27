#!/usr/bin/env bash
# convert-to-bare-repo.sh - Convert guitar-tone-shootout to bare repo + worktree structure
#
# This script creates a single directory containing:
#   guitar-tone-shootout-worktrees/
#   ├── guitar-tone-shootout.git/    # Bare repository (INSIDE worktrees folder)
#   ├── .worktree/                    # Registry
#   │   └── registry.db
#   ├── seed.sql                      # Shared seed data
#   ├── main/                         # Main worktree
#   └── [feature worktrees...]
#
# Run from anywhere - paths are absolute

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
WORK_DIR="/Users/ryanlauterbach/Work"
ORIGINAL_REPO="${WORK_DIR}/guitar-tone-shootout"
WORKTREE_ROOT="${WORK_DIR}/guitar-tone-shootout-worktrees"
BARE_REPO="${WORKTREE_ROOT}/guitar-tone-shootout.git"  # INSIDE worktrees folder
MAIN_WORKTREE="${WORKTREE_ROOT}/main"
REGISTRY_DIR="${WORKTREE_ROOT}/.worktree"
REGISTRY_DB="${REGISTRY_DIR}/registry.db"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

echo ""
echo "========================================="
echo "Guitar Tone Shootout - Bare Repo Conversion"
echo "========================================="
echo ""

# Pre-flight checks
log_step "Running pre-flight checks..."

if [ ! -d "$ORIGINAL_REPO" ]; then
    log_error "Original repo not found: $ORIGINAL_REPO"
    exit 1
fi

if [ -d "$WORKTREE_ROOT" ]; then
    log_error "Worktree root already exists: $WORKTREE_ROOT"
    echo "Remove it first if you want to re-run conversion:"
    echo "  rm -rf $WORKTREE_ROOT"
    exit 1
fi

# Check for uncommitted changes
cd "$ORIGINAL_REPO"
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    log_error "Uncommitted changes in original repo"
    echo "Commit or discard changes first:"
    echo "  git status"
    exit 1
fi

# Get current branch and remote URL
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
REMOTE_URL=$(git remote get-url origin)
log_info "Remote URL: $REMOTE_URL"
log_info "Current branch: $CURRENT_BRANCH"

# Confirm with user
echo ""
echo "This script will create a SINGLE directory containing:"
echo ""
echo "  $WORKTREE_ROOT/"
echo "  ├── guitar-tone-shootout.git/   # Bare repository"
echo "  ├── .worktree/registry.db       # SQLite registry"
echo "  ├── seed.sql                    # Shared seed data"
echo "  └── main/                       # Main worktree"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "Aborted by user"
    exit 0
fi

# Step 1: Create worktree root and registry directory
echo ""
log_step "Step 1: Creating worktree root structure..."
mkdir -p "$WORKTREE_ROOT"
mkdir -p "$REGISTRY_DIR"
log_info "Worktree root: $WORKTREE_ROOT"
log_info "Registry dir: $REGISTRY_DIR"

# Step 2: Clone as bare repo INSIDE worktrees folder
echo ""
log_step "Step 2: Creating bare repository (inside worktrees folder)..."
git clone --bare "$REMOTE_URL" "$BARE_REPO"
log_info "Bare repo created at: $BARE_REPO"

# Step 3: Create main worktree
echo ""
log_step "Step 3: Creating main worktree..."
cd "$BARE_REPO"
git worktree add "$MAIN_WORKTREE" main

# Configure git in worktree
cd "$MAIN_WORKTREE"
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch origin
log_info "Main worktree created at: $MAIN_WORKTREE"

# Step 4: Create shared model cache volume
echo ""
log_step "Step 4: Creating shared Docker volumes..."
docker volume create gts-model-cache 2>/dev/null || log_warn "Volume gts-model-cache may already exist"
log_info "Shared model cache volume: gts-model-cache"

# Step 5: Initialize SQLite registry
echo ""
log_step "Step 5: Initializing SQLite registry..."

# Create registry database with schema
python3 << 'PYTHON_SCRIPT'
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

registry_path = Path("/Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/.worktree/registry.db")

conn = sqlite3.connect(registry_path)
cursor = conn.cursor()

# Create schema
cursor.executescript("""
    -- Schema versioning
    CREATE TABLE IF NOT EXISTS schema_info (
        version TEXT PRIMARY KEY,
        migrated_at TEXT NOT NULL
    );

    -- Worktree registry
    CREATE TABLE IF NOT EXISTS worktrees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch TEXT NOT NULL UNIQUE,
        worktree_name TEXT NOT NULL UNIQUE,
        worktree_path TEXT NOT NULL,
        compose_project TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        offset INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        port_frontend INTEGER NOT NULL,
        port_backend INTEGER NOT NULL,
        port_db INTEGER NOT NULL,
        port_redis INTEGER NOT NULL,
        volume_postgres TEXT NOT NULL,
        volume_redis TEXT NOT NULL,
        volume_uploads TEXT NOT NULL
    );

    -- Git state tracking
    CREATE TABLE IF NOT EXISTS git_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        local_main_commit TEXT,
        remote_main_commit TEXT,
        last_synced_at TEXT
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_worktrees_status ON worktrees(status);
    CREATE INDEX IF NOT EXISTS idx_worktrees_offset ON worktrees(offset);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_worktrees_offset_active
        ON worktrees(offset) WHERE status = 'active';
""")

# Insert schema version
now = datetime.now(timezone.utc).isoformat()
cursor.execute(
    "INSERT OR REPLACE INTO schema_info (version, migrated_at) VALUES (?, ?)",
    ("1.0", now)
)

# Initialize git state singleton
cursor.execute(
    "INSERT OR IGNORE INTO git_state (id, last_synced_at) VALUES (1, ?)",
    (now,)
)

conn.commit()
conn.close()

print(f"SQLite registry initialized: {registry_path}")
PYTHON_SCRIPT

log_info "Registry database created: $REGISTRY_DB"

# Step 6: Create seed.sql placeholder
echo ""
log_step "Step 6: Creating seed.sql placeholder..."

cat > "${WORKTREE_ROOT}/seed.sql" << 'EOF'
-- Guitar Tone Shootout - Database Seed
-- This file is loaded into PostgreSQL on every worktree setup
--
-- To export current database state:
--   docker compose exec db pg_dump -U shootout --data-only shootout > ../seed.sql
--
-- To export schema + data:
--   docker compose exec db pg_dump -U shootout shootout > ../seed.sql
--
-- Note: Migrations are run AFTER seeding, so this file should contain
-- data compatible with the base schema (or be empty for fresh start)

-- Placeholder: Add seed data below
-- Example:
-- INSERT INTO users (tone3000_id, username) VALUES (1, 'testuser');
EOF

log_info "Seed file created: ${WORKTREE_ROOT}/seed.sql"

# Step 7: Create symlink to worktree.py for convenience
echo ""
log_step "Step 7: Creating worktree CLI symlink..."
if [ -f "${MAIN_WORKTREE}/worktree/worktree.py" ]; then
    ln -sf worktree/worktree.py "${MAIN_WORKTREE}/worktree.py"
    log_info "Symlink created: ${MAIN_WORKTREE}/worktree.py -> worktree/worktree.py"
else
    log_warn "worktree/worktree.py not found, skipping symlink"
fi

# Summary
echo ""
echo "========================================="
log_info "Conversion complete!"
echo "========================================="
echo ""
echo "Single directory structure created:"
echo ""
echo "  $WORKTREE_ROOT/"
echo "  ├── guitar-tone-shootout.git/   # Bare repository"
echo "  ├── .worktree/registry.db       # SQLite registry"
echo "  ├── seed.sql                    # Shared seed data"
echo "  └── main/                       # Main worktree"
echo ""
echo "Next steps:"
echo "  1. cd $MAIN_WORKTREE"
echo "  2. pip install -e worktree/"
echo "  3. ./worktree.py setup main"
echo "  4. docker compose up"
echo ""
log_warn "Original repo preserved at: $ORIGINAL_REPO"
echo "Delete it after verifying the new structure works:"
echo "  rm -rf $ORIGINAL_REPO"
echo ""
