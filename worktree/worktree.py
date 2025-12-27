#!/usr/bin/env python3
"""Git Worktree management CLI for Guitar Tone Shootout.

This is the entry point script. All logic is in the worktree package.

Usage:
    ./worktree.py --help
    ./worktree.py setup 42
    ./worktree.py list
    ./worktree.py teardown 42-feature-name
"""

from cli import main

if __name__ == "__main__":
    main()
