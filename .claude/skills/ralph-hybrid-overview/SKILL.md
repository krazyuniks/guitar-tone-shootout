---
name: ralph-hybrid-overview
description: Ralph Hybrid autonomous development workflow overview — planning, execution, verification, and GTS-specific customizations. Use when discussing Ralph Hybrid features, troubleshooting autonomous loops, or understanding the workflow.
---

# Ralph Hybrid Overview

Autonomous development loops for complex features.

## Workflow

```
1. Plan:    /ralph-hybrid-plan "description"   (in Claude Code)
2. Run:     ralph-hybrid run                    (in terminal)
3. Verify:  (automatic after stories complete)
4. Archive: ralph-hybrid archive               (or prompted after verify)
```

## When to Use

- Multi-story features (3+ related tasks)
- Features derived from GitHub issues
- Work that benefits from TDD iteration
- Autonomous implementation with human checkpoints

## Commands

| Command | Where | Purpose |
|---------|-------|---------|
| `/ralph-hybrid-plan` | Claude Code | Interactive planning, creates spec.md + prd.json |
| `/ralph-hybrid-plan --regenerate` | Claude Code | Regenerate prd.json from updated spec.md |
| `/ralph-hybrid-amend` | Claude Code | Modify requirements mid-implementation |
| `ralph-hybrid run` | Terminal | Execute autonomous loop |
| `ralph-hybrid run --skip-verification` | Terminal | Run without goal-backward verification |
| `ralph-hybrid verify` | Terminal | Run goal-backward verification manually |
| `ralph-hybrid status` | Terminal | Show feature progress |

## Key Concepts

- **Fresh context per iteration**: Each loop iteration starts Claude fresh
- **Memory in files**: prd.json tracks story completion, progress.txt logs history
- **Branch = feature folder**: `.ralph-hybrid/{branch-name}/` holds all state
- **Fail fast**: Circuit breaker trips after 2 same errors or no progress
- **Goal-backward verification**: After stories complete, verifies feature actually works

For GTS-specific customizations (backpressure hooks, project memories), see `references/gts-customizations.md`.
