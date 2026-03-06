<!-- domains: all -->
# Worktree Branching Rules
- NEVER create branches on the `main` worktree. The main worktree tracks the `main` branch — all commits go directly to `main`.
- Feature branches belong in their own worktrees, created via `./worktree.py setup <name>`.
- Each worktree IS a branch. Creating branches within a worktree causes race conditions with other sessions (staging area conflicts, pre-commit hook stash collisions).
- If you need a feature branch: STOP, ask the user to create a worktree for it.
