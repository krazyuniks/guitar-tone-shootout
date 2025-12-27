#!/usr/bin/env python3
"""Git Worktree management CLI for Guitar Tone Shootout.

This is the entry point script. All logic is in the worktree package.

Usage:
    ./worktree.py --help
    ./worktree.py setup 42
    ./worktree.py list
    ./worktree.py teardown 42-feature-name
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import worktree package
parent = Path(__file__).resolve().parent.parent
if str(parent) not in sys.path:
    sys.path.insert(0, str(parent))

from worktree.cli import main

if __name__ == "__main__":
    main()
