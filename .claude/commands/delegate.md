---
description: Execute a task using orchestrator workflow with sub-agent delegation.
allowed-tools: Bash(gh:*), Bash(worktree:*), Task
argument-hint: "<issue-number>"
context: fork
---

# /delegate - Execute Task with Orchestrator

Execute a task using the full orchestrator workflow with mandatory sub-agent delegation.

## Usage

```
/delegate <issue-number>
/delegate 250
```

## Orchestrator Role

You are the **orchestrator**. Your job is:
1. **Lifecycle management** - Setup, PR, CI monitoring, completion
2. **Delegation** - Implementation work goes to sub-agents
3. **Context conservation** - Stay lean, don't read implementation code yourself

## Workflow

### Phase 1: Discovery
```bash
gh issue view $ARGUMENTS --repo krazyuniks/guitar-tone-shootout
```

### Phase 2: Setup
```bash
worktree up gts $ARGUMENTS
```

### Phase 3: Delegate Implementation

**MUST use Task tool.** Do NOT implement yourself.

```
Task tool:
  description: "Implement <brief description>"
  subagent_type: "general-purpose"
  prompt: |
    ## Task: <title from issue>
    **Worktree:** <path>
    **Issue:** #<number>

    ### Requirements
    <from issue body>

    ### Rules
    - TDD: failing test first, then implement
    - Run `just check` before completing
    - Browser test if UI changes
    - Commit with descriptive message
```

### Phase 4: Create PR
```
/merge
```

### Phase 5: Enable Auto-Merge
```bash
gh pr merge <pr_number> --repo krazyuniks/guitar-tone-shootout --squash --auto
```

### Phase 6: CI Monitoring (MANDATORY)

Poll every 30 seconds:
```bash
gh pr view <pr_number> --repo krazyuniks/guitar-tone-shootout --json state,statusCheckRollup
```

| State | Action |
|-------|--------|
| `MERGED` | Proceed to completion |
| `CLOSED` | Report to human |
| CI `FAILURE` | Fix, push, resume polling |

### Phase 7: Completion

**Automatic.** When `gh pr view` shows MERGED, the `merge-teardown` hook runs automatically.

## Responsibility Matrix

| Orchestrator (you) | Sub-Agent (delegated) |
|--------------------|----------------------|
| `gh issue view` | Read/understand code |
| `worktree up gts <branch>` | Provision a feature worktree |
| `/merge` | Write tests |
| Poll CI | Browser testing |
| (auto teardown) | Fix issues |
