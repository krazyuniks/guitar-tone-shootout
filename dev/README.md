# Dev Docs Pattern

The **dev docs pattern** is a context persistence system that preserves project knowledge across Claude Code context resets, enabling developers to resume complex tasks in minutes instead of hours.

---

## The Problem: Context Resets Are Expensive

Claude Code has context limits. When context resets occur during complex tasks:
- **30+ minutes** spent reconstructing what was being done
- Lost decisions, file locations, and implementation approaches
- Broken flow and productivity loss
- Risk of repeating mistakes or inconsistent implementations

**After a reset, without dev docs, everything must be rediscovered from scratch.**

---

## The Solution: Structured Persistence

A comprehensive file structure that captures everything needed to resume work:

```
dev/
├── README.md                      (this file)
├── session-state.md               (SOURCE OF TRUTH: issue → dev-docs mapping)
├── EXECUTION-PLAN.md              (project-wide epic/phase tracking)
├── active/                        (current work)
│   └── [task-name]/
│       ├── [task-name]-plan.md      (task-specific strategic blueprint)
│       ├── [task-name]-context.md   (task-specific decisions + progress)
│       └── [task-name]-tasks.md     (task-specific checklist)
├── archive/                       (completed work for reference)
└── reference/                     (reusable patterns, not task-specific)
```

**File Scope Guide:**
- **session-state.md**: Registry of active issues and their dev-docs (check here first!)
- **EXECUTION-PLAN.md**: Project-wide epic execution plan (all epics)
- **active/[task-name]/**: Task-specific docs (1 epic/issue = 1 folder)
- **archive/**: Completed tasks (moved here after PR merged)

**These files survive context resets** - Claude reads them to resume instantly in <5 minutes.

---

## Three-File Structure

### 1. [task-name]-plan.md

**Purpose:** Strategic plan for the implementation

**Contains:**
- Executive summary
- Current state analysis
- Proposed architecture
- Implementation phases
- Risk assessment

**When to update:** When scope changes or new phases discovered

### 2. [task-name]-context.md

**Purpose:** Key information for resuming work

**Contains:**
- SESSION PROGRESS section (updated frequently!)
- What's completed vs in-progress
- Key files and their purposes
- Important decisions made
- Technical constraints discovered
- Quick resume instructions

**When to update:** **FREQUENTLY** - after major decisions, completions, or discoveries

### 3. [task-name]-tasks.md

**Purpose:** Checklist for tracking progress

**Contains:**
- Phases broken down by logical sections
- Tasks in checkbox format
- Status indicators
- Acceptance criteria

**When to update:** After completing each task or discovering new tasks

---

## Session Checkpoint Rules

**CRITICAL: Before suggesting a user start a new session or checkpoint:**

1. **MUST** create/update `dev/session-state.md`
2. **MUST** create `dev/active/[task]/` for any active work
3. **MUST** persist all architectural decisions to context.md
4. **NEVER** tell user to start new session without saving state first

A pre-commit hook enforces this - commits will fail if:
- Active GitHub issues exist but `dev/active/` is empty
- `session-state.md` is missing or stale

---

## Workflow

### Starting Complex Work

```bash
# 1. Create GitHub issue
gh issue create --title "feat: description"

# 2. Create dev-docs
mkdir -p dev/active/[task-name]
# Create plan.md, context.md, tasks.md

# 3. Update session-state.md
# Add issue → dev-docs mapping
```

### During Work

- Update `context.md` after each major decision
- Check off tasks in `tasks.md` as completed
- Update `session-state.md` if status changes

### Before Session End / Checkpoint

```bash
# 1. Update all dev-docs with current state
# 2. Commit changes
git add -A && git commit -m "checkpoint: description"

# 3. Push
git push
```

### Resuming Work

```bash
# 1. Read session-state.md first
cat dev/session-state.md

# 2. Read task-specific context
cat dev/active/[task-name]/[task-name]-context.md

# 3. Check tasks
cat dev/active/[task-name]/[task-name]-tasks.md
```

### Completing Work

```bash
# After PR merged
mv dev/active/[task-name] dev/archive/
# Update session-state.md to remove from active
```

---

## Quick Reference

```
┌─────────────────────────────────────────────────────────────────┐
│ Dev Docs Pattern - Quick Reference                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ WHEN TO USE                                                     │
│   ✅ Complex tasks >2 hours                                     │
│   ✅ Before context reset                                       │
│   ✅ Multi-file/layer changes                                   │
│   ✅ Architectural decisions                                    │
│                                                                 │
│ FILES                                                           │
│   [task]-plan.md       Strategic blueprint (rarely changes)     │
│   [task]-context.md    Progress + decisions (often changes)     │
│   [task]-tasks.md      Checklist (very often changes)           │
│                                                                 │
│ KEY PRINCIPLE                                                   │
│   "Can I resume in <5 min with just these files?"               │
│                                                                 │
│ CHECKPOINT RULE                                                 │
│   NEVER end session without saving state to dev-docs first!     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- **AGENTS.md** — Development workflow, quality gates, patterns
- **GitHub Issues** — `gh issue list --state open`
- **GitHub Milestones** — `gh milestone list`
