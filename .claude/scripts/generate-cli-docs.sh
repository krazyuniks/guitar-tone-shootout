#!/bin/bash
#
# Regenerates worktree-cli skill documentation from actual --help output.
# Run this whenever worktree.py commands or flags change.
#
# Usage: .claude/scripts/generate-cli-docs.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT="$PROJECT_ROOT/.claude/skills/worktree-cli/SKILL.md"

cd "$PROJECT_ROOT"

# Ensure worktree.py exists
if [ ! -f "./worktree.py" ]; then
    echo "Error: worktree.py not found in $PROJECT_ROOT"
    exit 1
fi

echo "Generating worktree-cli skill documentation..."

# Start with frontmatter and header
cat > "$OUTPUT" << 'HEADER'
---
name: worktree-cli
description: Git worktree management with worktree.py CLI. Use for creating worktrees, teardown, merging PRs, syncing branches, and Docker service management.
---

# worktree-cli Skill

**Auto-generated reference for `./worktree.py` commands.**

> This is the SOURCE OF TRUTH for worktree.py flags and options.
> Regenerate with: `.claude/scripts/generate-cli-docs.sh`

## When to Use This Skill

- Setting up new worktrees for issues
- Tearing down worktrees after PR merge
- Managing Docker services across worktrees
- Syncing worktrees after merges
- Troubleshooting worktree issues

## Quick Reference

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `setup <issue>` | Create worktree from GH issue | `--skip-db-import`, `--no-start`, `--build` |
| `complete <pr>` | **RECOMMENDED**: Full lifecycle completion | - |
| `teardown <name>` | Remove worktree only | `-f/--force`, `--keep-branch` |
| `list` | Show all worktrees | `-c/--compact` |
| `merge-pr <num>` | Merge PR + teardown | `--skip-sync`, `--skip-teardown` |
| `cleanup` | Remove merged branches | `-f/--force` (required to execute) |
| `logs` | View Docker logs | `-n <lines>`, `-f/--follow` |

**Prefer `complete` over `merge-pr`** - it handles issue closure and sync automatically.

## Common Workflows

### Start New Work
```bash
./worktree.py setup 42              # From issue number
cd ../42-feature-name
./worktree.py health                # Verify services
```

### Complete Work

**Automatic.** After PR merges, the `merge-teardown` hook runs automatically:
1. Closes GitHub issue
2. Switches to main
3. Runs `./worktree.py teardown`

Manual (if needed):
```bash
./worktree.py teardown 123/feature-name --force
```

### Maintenance
```bash
./worktree.py cleanup               # Dry-run: show what would be cleaned
./worktree.py cleanup --force       # Actually clean up merged branches
./worktree.py prune                 # Remove stale registry entries
```

---

## Command Reference

HEADER

# Generate each command's documentation
# All commands from worktree.py --help
COMMANDS="auth-status auth-login auth-restore seed backup db-reset sync prune prune-branches orphans list status health ports merge-pr complete cleanup version hooks check-stale validate is-fresh services-start stop logs start setup sync-start sync-stop teardown cleanup-orphans"

for cmd in $COMMANDS; do
    echo "  Processing: $cmd"

    echo "### $cmd" >> "$OUTPUT"
    echo "" >> "$OUTPUT"

    # Get the help output
    help_output=$(./worktree.py "$cmd" --help 2>&1)

    # Extract description (first non-empty line after Usage)
    description=$(echo "$help_output" | grep -A1 "Usage:" | tail -1 | sed 's/^[[:space:]]*//')
    if [ -n "$description" ] && [ "$description" != "Usage:"* ]; then
        echo "$description" >> "$OUTPUT"
        echo "" >> "$OUTPUT"
    fi

    echo '```' >> "$OUTPUT"
    # Strip ANSI escape codes (Rich formatting) for clean markdown
    echo "$help_output" | sed 's/\x1b\[[0-9;]*m//g' >> "$OUTPUT"
    echo '```' >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "---" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
done

# Add Auth Workflow section
cat >> "$OUTPUT" << 'AUTH_SECTION'
## Auth Workflow

**Initial authentication (once):**
```bash
./worktree.py setup 42              # Creates worktree
./worktree.py auth-login --port 8030  # Login via browser (uses worktree's backend)
```

**After that, all worktrees share the auth:**
```bash
./worktree.py setup 123             # Auto-restores auth from shared file
```

**Check status anytime:**
```bash
./worktree.py auth-status
```

---

AUTH_SECTION

# Add common mistakes section
cat >> "$OUTPUT" << 'FOOTER'
## Common Mistakes to Avoid

| Wrong | Right | Why |
|-------|-------|-----|
| `prune --force` | `prune` | prune has no --force flag |
| `cleanup` alone | `cleanup --force` | cleanup is dry-run by default |
| `teardown` on main | Never teardown main | main is the base worktree |
| Manual `git pull` after merge | `complete <num>` | complete handles sync + issue closure |
| `merge-pr` alone | `complete <num>` | complete is the recommended full lifecycle |
FOOTER

echo ""
echo "Generated: $OUTPUT"
echo "Lines: $(wc -l < "$OUTPUT")"
