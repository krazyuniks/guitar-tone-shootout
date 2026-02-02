# /ralph-hybrid-amend - Mid-Implementation Scope Changes

Safely modify requirements during active Ralph development. Plans evolve. Requirements get clarified. This command handles scope changes without losing progress.

## Why This Matters

> **"No plan survives first contact with implementation."**

First drafts are incomplete. Edge cases emerge. Stakeholders clarify requirements. This is normal. Ralph Hybrid embraces iterative refinement through `/ralph-hybrid-amend`:

- **ADD** new requirements discovered during implementation
- **CORRECT** existing stories when requirements are clarified
- **REMOVE** stories that are descoped or moved elsewhere

All changes are tracked, auditable, and preserve completed work.

---

## Arguments

```
/ralph-hybrid-amend <mode> [target] [description] [--insert-after STORY-ID]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `mode` | Yes | `add`, `correct`, `remove`, or `status` |
| `target` | For correct/remove | Story ID (e.g., `STORY-003`) |
| `description` | For add/correct | Brief description of change |
| `--insert-after` | Optional | Insert new story after specified story ID (uses decimal ID) |

### Examples

```bash
/ralph-hybrid-amend add "Users need CSV export for reporting"
/ralph-hybrid-amend add "Urgent fix needed" --insert-after STORY-002
/ralph-hybrid-amend correct STORY-003 "Email validation should use RFC 5322"
/ralph-hybrid-amend remove STORY-005 "Moved to separate issue #47"
/ralph-hybrid-amend status
```

---

## Mode: ADD

Add new requirements discovered during implementation.

### Workflow

```
1. VALIDATE   - Confirm feature folder exists, Ralph not mid-iteration
2. CLARIFY    - Mini-planning session (2-3 questions max)
3. DEFINE     - Create acceptance criteria
4. SIZE       - Check if story needs splitting
5. INTEGRATE  - Update spec.md and prd.json
6. LOG        - Record amendment in progress.txt
7. CONFIRM    - Show summary, ready to continue
```

### Phase 1: VALIDATE

```bash
# Check we're in a valid state
feature_dir=$(detect_feature_dir)
if [ ! -f "$feature_dir/prd.json" ]; then
    error "No active feature. Run /ralph-hybrid-plan first."
fi

# Check Ralph isn't mid-iteration (optional - can interrupt)
if ralph_is_running; then
    warn "Ralph is currently running. Interrupt to add requirement? (y/N)"
fi
```

### Phase 2: CLARIFY

Ask focused questions to understand the new requirement:

```
You want to add: "Users need CSV export for reporting"

Let me clarify a few things:

1. What data should be exportable?
   A) Current view/filtered data only
   B) All user data
   C) Specific data types (specify)

2. Any format requirements?
   A) Simple CSV (comma-separated)
   B) CSV with headers
   C) Multiple format options (CSV, JSON, Excel)

3. Is this blocking other work, or additive?
   A) Blocking - needed before feature is complete
   B) Additive - nice to have, can be last
```

**Rules:**
- Maximum 3 questions
- Multiple choice where possible
- Skip obvious questions based on context

### Phase 3: DEFINE

Generate acceptance criteria following project standards:

```markdown
**Acceptance Criteria:**
- [ ] Export button visible on data list view
- [ ] Clicking export downloads CSV file
- [ ] CSV includes column headers
- [ ] CSV includes all visible/filtered rows
- [ ] Filename includes timestamp: `export-{timestamp}.csv`
- [ ] Typecheck passes
- [ ] Unit tests pass
```

**Present to user:**
```
Here are the acceptance criteria I've drafted:
[shows criteria]

Look good? (Y/n/edit)
```

### Phase 4: SIZE

Check if story should be split:

```
Size check:
- Acceptance criteria: 7 items ✓ (≤8 is fine)
- Estimated files: 2-3 ✓ (≤4 is fine)
- Complexity: Medium ✓

Story size is appropriate. No split needed.
```

**If oversized:**
```
This requirement seems large. I suggest splitting:

STORY-004: Add export button and CSV generation
STORY-005: Add format selection (CSV/JSON/Excel)

Split into multiple stories? (Y/n)
```

### Phase 5: INTEGRATE

Update all relevant files.

#### Using `--insert-after` for Urgent Stories

When you need to insert a story immediately after a specific story (rather than appending to the end), use the `--insert-after` flag:

```bash
/ralph-hybrid-amend add "Critical security fix" --insert-after STORY-002
```

This creates a **decimal story ID** (e.g., `STORY-002.1`) that:
- Inserts logically after STORY-002 but before STORY-003
- Preserves existing story numbering (no renumbering needed)
- Allows multiple insertions: STORY-002.1, STORY-002.2, STORY-002.3, etc.
- Supports nested insertions: STORY-002.1, then STORY-002.2 between .1 and .3

**Decimal ID Ordering:**
- Decimal parts are treated as integers: STORY-002.9 < STORY-002.10
- Stories sort automatically: 001, 002, 002.1, 002.2, 003, 003.1, 004
- No limit on decimal values: STORY-002.99 is valid

**Example with --insert-after:**

**spec.md** - Append to Amendments section:

```markdown
---

## Amendments

### AMD-001: CSV Export (2026-01-09T14:32:00Z)

**Type:** ADD
**Reason:** User needs data export for external reporting
**Added by:** /ralph-hybrid-amend

#### STORY-004: Export data as CSV

**As a** user
**I want to** export my data as CSV
**So that** I can analyze it in spreadsheets

**Acceptance Criteria:**
- [ ] Export button visible on data list view
- [ ] Clicking export downloads CSV file
- [ ] CSV includes column headers
- [ ] CSV includes all visible/filtered rows
- [ ] Filename includes timestamp
- [ ] Typecheck passes
- [ ] Unit tests pass

**Priority:** 2 (after current stories)

**Technical Notes:**
- Use existing data fetch logic
- Implement in frontend, no new API needed
```

**prd.json** - Add new story:

```json
{
  "userStories": [
    // ... existing stories preserved ...
    {
      "id": "STORY-004",
      "title": "Export data as CSV",
      "description": "As a user I want to export my data as CSV so that I can analyze it in spreadsheets",
      "acceptanceCriteria": [
        "Export button visible on data list view",
        "Clicking export downloads CSV file",
        "CSV includes column headers",
        "CSV includes all visible/filtered rows",
        "Filename includes timestamp",
        "Typecheck passes",
        "Unit tests pass"
      ],
      "priority": 2,
      "passes": false,
      "notes": "",
      "amendment": {
        "id": "AMD-001",
        "type": "add",
        "timestamp": "2026-01-09T14:32:00Z",
        "reason": "User needs data export for external reporting"
      }
    }
  ]
}
```

### Phase 6: LOG

Append to progress.txt:

```
---
## Amendment AMD-001: 2026-01-09T14:32:00Z

Type: ADD
Command: /ralph-hybrid-amend add "Users need CSV export for reporting"

Added Stories:
  - STORY-004: Export data as CSV (priority: 2)

Reason: User needs data export for external reporting

Files Updated:
  - spec.md: Added Amendments section
  - prd.json: Added STORY-004

Context: Discovered during STORY-002 implementation that users
need to export filtered results for monthly reporting.

---
```

### Phase 7: CONFIRM

```
Amendment AMD-001 complete.

Added:
  STORY-004: Export data as CSV
  Priority: 2 (will run after current stories)
  Acceptance criteria: 7 items

Updated files:
  ✓ spec.md    - Added Amendments section
  ✓ prd.json   - Added STORY-004 (passes: false)
  ✓ progress.txt - Logged AMD-001

Current progress:
  ✓ STORY-001 (passes: true)
  ✓ STORY-002 (passes: true)
  → STORY-003 (passes: false) - in progress
  + STORY-004 (passes: false) - NEW

Ready to continue: ralph-hybrid run
```

---

## Mode: CORRECT

Fix or clarify existing story requirements.

### Workflow

```
1. VALIDATE   - Confirm story exists
2. SHOW       - Display current story definition
3. IDENTIFY   - What needs to change?
4. WARN       - If passes: true, warn about reset
5. UPDATE     - Modify spec.md and prd.json
6. LOG        - Record correction in progress.txt
7. CONFIRM    - Show diff and summary
```

### Phase 1-2: VALIDATE & SHOW

```
/ralph-hybrid-amend correct STORY-003 "Email validation needs RFC 5322"

Found STORY-003: Validate user registration input

Current definition:
  As a: system
  I want to: validate user input on registration
  So that: invalid data doesn't enter the system

  Acceptance Criteria:
  - [ ] Email field is required
  - [ ] Password minimum 8 characters
  - [ ] Username alphanumeric only
  - [ ] Typecheck passes
  - [ ] Unit tests pass

  Status: passes: false (in progress)
```

### Phase 3: IDENTIFY

```
What needs to change?

A) Acceptance criteria only
B) Story description
C) Both description and criteria
D) Add technical notes

Your input: "Email validation needs RFC 5322"

I understand you want to update the email validation criterion.

Current: "Email field is required"
Proposed: "Email validated against RFC 5322 format"

Is this correct? (Y/n/elaborate)
```

### Phase 4: WARN (if applicable)

```
⚠️  Warning: STORY-003 has passes: true

This story was marked complete. Correcting it will:
  - Reset passes: true → false
  - Require re-verification in next Ralph run
  - Previous implementation may need updates

Proceed with correction? (y/N)
```

### Phase 5: UPDATE

**spec.md** - Add correction note:

```markdown
### AMD-002: STORY-003 Correction (2026-01-09T15:10:00Z)

**Type:** CORRECT
**Target:** STORY-003 - Validate user registration input
**Reason:** Email validation was underspecified

**Changes:**
| Field | Before | After |
|-------|--------|-------|
| Acceptance Criteria #1 | Email field is required | Email validated against RFC 5322 format |

**Status Impact:** passes reset to false (re-verification required)
```

**prd.json** - Update story:

```json
{
  "id": "STORY-003",
  "title": "Validate user registration input",
  "acceptanceCriteria": [
    "Email validated against RFC 5322 format",  // Changed
    "Password minimum 8 characters",
    "Username alphanumeric only",
    "Typecheck passes",
    "Unit tests pass"
  ],
  "passes": false,  // Reset if was true
  "notes": "AMD-002: Email validation clarified to RFC 5322",
  "amendment": {
    "id": "AMD-002",
    "type": "correct",
    "timestamp": "2026-01-09T15:10:00Z",
    "reason": "Email validation was underspecified",
    "changes": {
      "acceptanceCriteria": {
        "before": ["Email field is required", "..."],
        "after": ["Email validated against RFC 5322 format", "..."]
      },
      "passesReset": true
    }
  }
}
```

### Phase 6-7: LOG & CONFIRM

```
Amendment AMD-002 complete.

Corrected:
  STORY-003: Validate user registration input

Changes:
  - Criterion 1: "Email field is required" → "Email validated against RFC 5322 format"
  - Status: passes reset to false

Updated files:
  ✓ spec.md     - Added AMD-002 correction note
  ✓ prd.json    - Updated STORY-003
  ✓ progress.txt - Logged AMD-002

Next Ralph run will re-verify STORY-003.

Ready to continue: ralph-hybrid run
```

---

## Mode: REMOVE

Descope a story (move elsewhere, no longer needed, etc.).

### Workflow

```
1. VALIDATE   - Confirm story exists
2. SHOW       - Display story and its status
3. CONFIRM    - Require reason for removal
4. ARCHIVE    - Move to descoped section (don't delete)
5. UPDATE     - Remove from active stories in prd.json
6. LOG        - Record removal in progress.txt
7. CONFIRM    - Show summary
```

### Key Behavior

**Stories are never deleted** - they're moved to a "Descoped" section for audit trail:

```markdown
## Descoped Stories

### STORY-005: Advanced filtering (Removed AMD-003)

**Removed:** 2026-01-09T16:00:00Z
**Reason:** Moved to separate issue #47 for Phase 2
**Status at removal:** passes: false

**Original Definition:**
[full story preserved here]
```

### Example Flow

```
/ralph-hybrid-amend remove STORY-005 "Moved to separate issue #47"

Found STORY-005: Advanced filtering options

Status: passes: false (not started)
Priority: 3

This will:
  - Remove STORY-005 from active prd.json stories
  - Archive to "Descoped" section in spec.md
  - Log removal in progress.txt

Confirm removal? (y/N)
```

```
Amendment AMD-003 complete.

Removed:
  STORY-005: Advanced filtering options
  Reason: Moved to separate issue #47

Archived to: spec.md → Descoped Stories section

Current progress:
  ✓ STORY-001 (passes: true)
  ✓ STORY-002 (passes: true)
  → STORY-003 (passes: false)
  + STORY-004 (passes: false)
  ✗ STORY-005 (descoped)

Ready to continue: ralph-hybrid run
```

---

## Mode: STATUS

Show current amendment history and feature state.

```
/ralph-hybrid-amend status

Feature: feature-21-sync-implementation
Branch: feature/21-sync-implementation

Stories:
  ✓ STORY-001: Initialize sync service      (passes: true)
  ✓ STORY-002: Implement pull operation     (passes: true)
  → STORY-003: Implement push operation     (passes: false)
  + STORY-004: Add conflict resolution      (passes: false) [AMD-001]
  ✗ STORY-005: Advanced merge strategies    (descoped) [AMD-002]

Amendments:
  AMD-001 (2026-01-09T14:32:00Z) ADD     - STORY-004 added
  AMD-002 (2026-01-09T15:45:00Z) REMOVE  - STORY-005 descoped

Progress: 2/4 stories complete (50%)

Files:
  spec.md      - 2 amendments recorded
  prd.json     - 4 active stories
  progress.txt - 12 entries
```

---

## Amendment ID Format

Amendments are tracked with sequential IDs per feature:

```
AMD-001  # First amendment
AMD-002  # Second amendment
AMD-NNN  # Sequential within feature
```

IDs are:
- Unique per feature (not global)
- Referenced in spec.md, prd.json, and progress.txt
- Never reused (even if amendment is reverted)

---

## Edge Cases

### Adding to completed feature

```
/ralph-hybrid-amend add "One more thing..."

⚠️  All stories currently pass. Adding new story will:
  - Mark feature incomplete
  - Require additional Ralph runs

Proceed? (y/N)
```

### Correcting a story that blocks others

```
/ralph-hybrid-amend correct STORY-001 "Change API contract"

⚠️  STORY-001 is a dependency for:
  - STORY-002 (passes: true)
  - STORY-003 (passes: false)

Correcting may invalidate dependent stories.
Reset all dependent stories? (y/N/select)
```

### Removing a blocking story

```
/ralph-hybrid-amend remove STORY-002 "Not needed"

⚠️  STORY-002 blocks:
  - STORY-003 (passes: false)
  - STORY-004 (passes: false)

Options:
  A) Remove STORY-002, keep dependent stories
  B) Remove STORY-002 and all dependent stories
  C) Cancel

Choice:
```

### Conflicting amendments

```
/ralph-hybrid-amend correct STORY-003 "New requirement"

⚠️  STORY-003 was already amended:
  - AMD-001 (2026-01-09T14:00:00Z): Added acceptance criterion

This correction will be AMD-002, building on AMD-001.
Continue? (Y/n)
```

---

## Integration with Ralph Loop

Ralph's prompt template should acknowledge amendments:

```markdown
## Context Files

- **prd.json**: User stories with completion status
- **progress.txt**: Iteration log AND amendment history
- **spec.md**: Original spec AND amendments section

## Amendment Awareness

When you see stories with `amendment` field in prd.json:
- These were added/modified after initial planning
- Check progress.txt for context on why
- Amendments marked with AMD-XXX in spec.md have full details

Amendments are normal. Plans evolve. Implement them like any other story.
```

---

## Error Messages

```
# No feature active
Error: No active feature found.
Run /ralph-hybrid-plan to create a feature first.

# Story not found
Error: STORY-099 not found in prd.json.
Available stories: STORY-001, STORY-002, STORY-003

# Invalid mode
Error: Unknown mode 'update'.
Valid modes: add, correct, remove, status

# Missing description
Error: ADD mode requires a description.
Usage: /ralph-hybrid-amend add "description of new requirement"

# Missing target
Error: CORRECT mode requires a story ID.
Usage: /ralph-hybrid-amend correct STORY-003 "what to change"
```

---

## Examples

### Example 1: Discovery during implementation

```
# Implementing STORY-002, realize we need error handling
/ralph-hybrid-amend add "Need retry logic for failed sync operations"

> Clarifying: What triggers a retry?
A) Automatic on any failure
B) Only network failures
C) User-initiated

> A

> How many retries before giving up?
A) 3 attempts
B) 5 attempts
C) Configurable

> A

Amendment AMD-001 complete.
Added STORY-004: Implement retry logic for sync failures
```

### Example 2: Stakeholder clarification

```
# Product clarifies a requirement mid-sprint
/ralph-hybrid-amend correct STORY-003 "Sync should be bidirectional, not just pull"

> Found STORY-003: Implement sync pull operation
>
> This is a significant change. The story currently only covers pull.
> Should I:
> A) Update STORY-003 to cover both directions
> B) Keep STORY-003 as pull, add STORY-004 for push
>
> B (separate concerns)

Amendment AMD-002 complete.
- STORY-003 unchanged (pull only)
- Added STORY-004: Implement sync push operation
```

### Example 3: Descoping for MVP

```
# Realize offline mode is too complex for v1
/ralph-hybrid-amend remove STORY-005 "Defer offline mode to v2, tracked in issue #89"

> Removing STORY-005: Offline mode support
> Reason: Defer offline mode to v2, tracked in issue #89
>
> Archived to spec.md Descoped section.
> Linked issue #89 noted for future reference.

Amendment AMD-003 complete.
Feature now has 4 active stories (was 5).
```

---

## Summary

| Mode | Purpose | Preserves Progress | Audit Trail |
|------|---------|-------------------|-------------|
| `add` | New requirement discovered | Yes | spec.md + progress.txt |
| `correct` | Clarify/fix existing | Yes (warns if resetting) | spec.md + progress.txt |
| `remove` | Descope story | Yes | Archived in spec.md |
| `status` | View amendments | N/A | N/A |

**Key principle:** Plans are living documents. `/ralph-hybrid-amend` makes scope changes safe, tracked, and reversible.
