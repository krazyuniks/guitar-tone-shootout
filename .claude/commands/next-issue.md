---
description: Find highest priority unblocked issue ready for work.
allowed-tools: Bash(gh:*)
---

# /next-issue - Find Next Issue

Find the highest priority unblocked issue ready for work.

## Steps

1. **Check P0 (critical) issues first:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "-is:blocked label:priority:P0 is:open" --limit 5
   ```

2. **If no P0s, check P1 (high priority):**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "-is:blocked label:priority:P1 is:open" --limit 5
   ```

3. **If no P1s, show all unblocked issues:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "-is:blocked is:open" --limit 10
   ```

## Output Format

```
Ready to work (unblocked):

P0 Critical:
  (none)

P1 High:
  #357 - Add audio waveform visualization [feature]
  #359 - Fix login redirect issue [bug]

Other:
  #361 - Update documentation [docs]

Recommendation: Start with #359 (bug fix, P1)
```

## Notes

- `-is:blocked` finds issues ready to work
- Consider unassigned issues first
- Use `/deps <number>` before claiming if unsure
