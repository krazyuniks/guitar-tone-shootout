"""Context assembly for the V2 epic planner.

This module delegates to workflow/context_assembler.py which implements
selective context injection based on area detection.

Usage:
    python scripts/context_assembler.py <epic_number>

Prefer the workflow module directly for new code:
    python workflow/context_assembler.py --epic-dir .planning/epics/E95/ --project-root .
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is on sys.path so workflow/ is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Re-export public API from the canonical location
from workflow.context_assembler import (  # noqa: E402
    AssemblyError,
    assemble_context,
)

PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"


def main() -> None:
    """CLI entry point: python scripts/context_assembler.py <epic_number>."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <epic_number>", file=sys.stderr)
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(
            f"Error: epic_number must be an integer, got: {sys.argv[1]}",
            file=sys.stderr,
        )
        sys.exit(1)

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(
            f"Error: Epic directory not found: {epic_dir}. "
            f"Run ingestion first: python scripts/epic_ingest.py {epic_number}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        path = assemble_context(epic_dir, PROJECT_ROOT)
        print(f"Assembled context for epic #{epic_number} at " f"{path.relative_to(PROJECT_ROOT)}")
    except AssemblyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
