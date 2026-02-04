#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.9.0",
#     "rich>=13.0",
#     "pydantic>=2.0",
#     "pydantic-settings>=2.0",
#     "pyyaml>=6.0",
#     "jinja2>=3.1.0",
#     "httpx>=0.25.0",
# ]
# ///
"""Git Worktree management CLI for Guitar Tone Shootout.

This is the entry point script. All logic is in the worktree package.
Dependencies are managed inline (PEP 723) and auto-installed by uv.

Usage:
    ./worktree.py --help
    ./worktree.py setup main
    ./worktree.py list
    ./worktree.py teardown 42-feature-name
    ./worktree.py info
"""

import sys
from pathlib import Path

# Add current directory to path so we can import worktree package
current = Path(__file__).resolve().parent
if str(current) not in sys.path:
    sys.path.insert(0, str(current))

from worktree.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
