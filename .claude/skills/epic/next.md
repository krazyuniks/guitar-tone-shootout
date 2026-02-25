---
name: next
description: Find highest priority unblocked issue ready for work.
context: current
---

# /epic next - Find Next Issue

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

4. **For each candidate, check if it's a parent:**
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<number>/sub_issues \
     --jq '.[] | {number, title, state}'
   ```
   If the result is non-empty, skip it (parent issues can't be run directly) and suggest the unblocked children instead.

## Output Format

```
Ready to work (unblocked leaf issues):

P0 Critical:
  (none)

P1 High:
  #130 - Audio pipeline setup [feature]
  #131 - Fix login redirect [bug]

Other:
  #135 - Update documentation [docs]

Skipped (parent issues — run children instead):
  #125 - Architecture Migration (3 children: #120, #121, #122)

Recommendation: Start with #131 (bug fix, P1)
```

## Notes

- `-is:blocked` finds issues ready to work
- Parent issues (with sub-issues) are listed separately — they can't be run as epics
- Use `/epic deps <number>` before claiming if unsure about dependencies
