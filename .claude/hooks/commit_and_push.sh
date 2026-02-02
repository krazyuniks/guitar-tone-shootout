#!/bin/bash
# /commit_and_push - Commit and push changes
#
# Usage: .claude/hooks/commit_and_push.sh ["commit message"]
#
# Commits all changes and pushes to remote:
# 1. Write session state
# 2. Stage all changes
# 3. Commit (with message or auto-generate)
# 4. Push

set -e

GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$GIT_ROOT" ] && { echo "Not in a git repo"; exit 1; }
cd "$GIT_ROOT"

COMMIT_MSG="$1"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  /commit_and_push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Write session state
if [ -x ".claude/hooks/write-session-state.sh" ]; then
    .claude/hooks/write-session-state.sh >/dev/null 2>&1 && echo "✓ Session state written" || echo "⚠ Session state failed"
fi

# 2. Check for changes
if git diff --quiet HEAD 2>/dev/null && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "✓ No changes to commit"
else
    # 3. Stage all
    git add -A

    # 4. Generate commit message if not provided
    if [ -z "$COMMIT_MSG" ]; then
        # Auto-generate from changed files
        CHANGED=$(git diff --cached --name-only | head -5 | tr '\n' ', ' | sed 's/,$//')
        COMMIT_MSG="chore: update $CHANGED"
    fi

    # Add standard footer
    FULL_MSG="$COMMIT_MSG

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

    # 5. Commit
    git commit -m "$FULL_MSG" && echo "✓ Committed: $COMMIT_MSG" || echo "⚠ Commit failed"
fi

# 6. Push
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if git push origin "$BRANCH" 2>/dev/null; then
    echo "✓ Pushed to origin/$BRANCH"
else
    echo "⚠ Push failed (may need force push or branch protection)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Changes committed and pushed."
echo "  Run /merge to create PR and merge."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
