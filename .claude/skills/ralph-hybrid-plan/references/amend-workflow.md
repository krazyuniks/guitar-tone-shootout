# Mid-Implementation Amendments

Safely modify requirements during active Ralph development. Plans evolve. Requirements get clarified. This handles scope changes without losing progress.

## Usage

```
/ralph-hybrid-amend <mode> [target] [description] [--insert-after STORY-ID]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `mode` | Yes | `add`, `correct`, `remove`, or `status` |
| `target` | For correct/remove | Story ID (e.g., `STORY-003`) |
| `description` | For add/correct | Brief description of change |
| `--insert-after` | Optional | Insert new story after specified ID (uses decimal ID) |

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

### Using `--insert-after` for Urgent Stories

Creates a **decimal story ID** (e.g., `STORY-002.1`) that:
- Inserts logically after STORY-002 but before STORY-003
- Preserves existing story numbering (no renumbering)
- Allows multiple insertions: STORY-002.1, STORY-002.2, STORY-002.3
- Decimal parts treated as integers: STORY-002.9 < STORY-002.10

### Integration

**spec.md** - Append to Amendments section:

```markdown
## Amendments

### AMD-001: CSV Export (2026-01-09T14:32:00Z)

**Type:** ADD
**Reason:** User needs data export for external reporting
**Added by:** /ralph-hybrid-amend

#### STORY-004: Export data as CSV
...
```

**prd.json** - Add new story with `amendment` field:

```json
{
  "id": "STORY-004",
  "title": "Export data as CSV",
  "passes": false,
  "amendment": {
    "id": "AMD-001",
    "type": "add",
    "timestamp": "2026-01-09T14:32:00Z",
    "reason": "User needs data export for external reporting"
  }
}
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

**Warning for completed stories:**
```
Warning: STORY-003 has passes: true
Correcting will reset passes: true -> false and require re-verification.
Proceed? (y/N)
```

---

## Mode: REMOVE

Descope a story (move elsewhere, no longer needed).

**Stories are never deleted** -- they're moved to a "Descoped" section for audit trail:

```markdown
## Descoped Stories

### STORY-005: Advanced filtering (Removed AMD-003)

**Removed:** 2026-01-09T16:00:00Z
**Reason:** Moved to separate issue #47 for Phase 2
**Status at removal:** passes: false

**Original Definition:**
[full story preserved here]
```

---

## Mode: STATUS

Show current amendment history and feature state:

```
Feature: feature-21-sync-implementation
Stories:
  STORY-001 (passes: true)
  STORY-002 (passes: true)
  STORY-003 (passes: false) - in progress
  STORY-004 (passes: false) [AMD-001]
  STORY-005 (descoped) [AMD-002]

Amendments:
  AMD-001 (ADD) - STORY-004 added
  AMD-002 (REMOVE) - STORY-005 descoped

Progress: 2/4 stories complete (50%)
```

---

## Amendment ID Format

Sequential IDs per feature: AMD-001, AMD-002, AMD-NNN. Never reused, even if reverted.

---

## Edge Cases

### Adding to completed feature
Warn that adding new story marks feature incomplete.

### Correcting a story that blocks others
Warn about dependent stories, offer to reset dependents.

### Removing a blocking story
Options: remove only, remove with dependents, or cancel.

### Conflicting amendments
Note existing amendments, create new amendment building on previous.

---

## Integration with Ralph Loop

Ralph's prompt template acknowledges amendments:
- Stories with `amendment` field were added/modified after initial planning
- Check progress.txt for context on why
- Amendments are normal -- implement like any other story

---

## Summary

| Mode | Purpose | Preserves Progress | Audit Trail |
|------|---------|-------------------|-------------|
| `add` | New requirement discovered | Yes | spec.md + progress.txt |
| `correct` | Clarify/fix existing | Yes (warns if resetting) | spec.md + progress.txt |
| `remove` | Descope story | Yes | Archived in spec.md |
| `status` | View amendments | N/A | N/A |

**Key principle:** Plans are living documents. Amendments make scope changes safe, tracked, and reversible.
