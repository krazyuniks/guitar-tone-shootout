#!/usr/bin/env bash
# Ruff lint/format — routes files to Docker or host based on path.
#
# App code (libs/, apps/, sources/, tests/, scripts/) → Docker container
# Infra code (worktree/, workflow/, worktree.py) → host via uvx
#
# Fails hard if Docker is not running (for app code).
# Version pinned in pyproject.toml — single source of truth.

set -euo pipefail

mode="${1:?Usage: ruff-hook.sh check|format [files...]}"
shift

if [[ $# -eq 0 ]]; then
    exit 0
fi

project_root="$(git rev-parse --show-toplevel)"

# Separate files into Docker-routed and host-routed
docker_files=()
host_files=()

for f in "$@"; do
    rel="${f#"$project_root"/}"
    case "$rel" in
        worktree/*|worktree.py|workflow/*)
            host_files+=("$f")
            ;;
        *)
            docker_files+=("/app/$rel")
            ;;
    esac
done

exit_code=0

# Run Docker-routed files
if [[ ${#docker_files[@]} -gt 0 ]]; then
    case "$mode" in
        check)
            docker compose exec -T webapp ruff check --fix "${docker_files[@]}" || exit_code=$?
            ;;
        format)
            docker compose exec -T webapp ruff format "${docker_files[@]}" || exit_code=$?
            ;;
    esac
fi

# Run host-routed files with same version from container
if [[ ${#host_files[@]} -gt 0 ]]; then
    # Extract pinned version from pyproject.toml
    ruff_version=$(grep -oP 'ruff==\K[0-9.]+' "$project_root/pyproject.toml")
    case "$mode" in
        check)
            uvx "ruff@${ruff_version}" check --fix "${host_files[@]}" || exit_code=$?
            ;;
        format)
            uvx "ruff@${ruff_version}" format "${host_files[@]}" || exit_code=$?
            ;;
    esac
fi

exit "$exit_code"
