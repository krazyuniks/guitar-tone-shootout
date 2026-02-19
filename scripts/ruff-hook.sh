#!/usr/bin/env bash
# Ruff lint/format hook — runs on host via uvx with version pinned in pyproject.toml.
#
# All files run through `uvx ruff@<version>` on the host. Docker source mounts
# are read-only (:ro), so ruff format/check --fix cannot write inside containers.

set -euo pipefail

mode="${1:?Usage: ruff-hook.sh check|format [files...]}"
shift

if [[ $# -eq 0 ]]; then
    exit 0
fi

project_root="$(git rev-parse --show-toplevel)"
ruff_version=$(sed -n 's/.*ruff==\([0-9.]*\).*/\1/p' "$project_root/pyproject.toml" | head -1)

case "$mode" in
    check)
        uvx "ruff@${ruff_version}" check --fix "$@"
        ;;
    format)
        uvx "ruff@${ruff_version}" format "$@"
        ;;
esac
