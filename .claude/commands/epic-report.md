---
description: "[DEPRECATED] Use /epic-review instead. Comprehensive post-mortem review."
allowed-tools: Read
argument-hint: "<epic-number>"
context: fork
---

# /epic-report — DEPRECATED

This command has been superseded by `/epic-review`, which provides:
- Per-task metrics and agent effectiveness analysis
- Task complexity analysis with split recommendations
- Infrastructure issue tracking
- Learnings extraction and promotion recommendations
- Machine-readable `review-data.json` companion file

## Migration

```
/epic-review <epic-number>
```

Run `/epic-review` instead. It produces everything `/epic-report` did plus comprehensive post-mortem analysis.
