#!/bin/bash
# Quality Check Hook (PostToolUse on Edit|Write)
#
# Suggests running quality gates after file modifications.
# Non-blocking - provides hints, doesn't fail operations.

set -e

# Read tool result from stdin
INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Determine file type and suggest appropriate checks
case "$FILE_PATH" in
    backend/*.py|backend/**/*.py)
        echo ""
        echo "Python file modified in backend/. Consider running:"
        echo "  docker compose exec backend ruff check app/"
        echo "  docker compose exec backend mypy app/"
        echo "  just check-backend"
        ;;
    frontend/*.ts|frontend/*.tsx|frontend/*.astro|frontend/**/*.ts|frontend/**/*.tsx|frontend/**/*.astro)
        echo ""
        echo "Frontend file modified. Consider running:"
        echo "  docker compose exec frontend pnpm lint"
        echo "  docker compose exec frontend pnpm build"
        echo "  just check-frontend"
        ;;
    pipeline/*.py|pipeline/**/*.py)
        echo ""
        echo "Pipeline file modified. Consider running:"
        echo "  cd pipeline && just check"
        ;;
    **/alembic/**/*.py)
        echo ""
        echo "Migration file modified. Run migrations with:"
        echo "  docker compose exec backend alembic upgrade head"
        ;;
    docker-compose*.yml|**/Dockerfile*)
        echo ""
        echo "Docker configuration modified. Rebuild with:"
        echo "  docker compose build"
        echo "  docker compose up"
        ;;
esac
