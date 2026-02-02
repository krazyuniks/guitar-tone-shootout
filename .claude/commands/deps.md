---
description: Show dependency graph for a GitHub issue.
allowed-tools: Bash(gh:*)
argument-hint: "<issue-number>"
---

# /deps - Show Issue Dependencies

Display the dependency graph for a specific GitHub issue.

## Usage

```
/deps <issue-number>
/deps 357
```

## Steps

1. **Get issue details:**
   ```bash
   gh issue view <number> --repo krazyuniks/guitar-tone-shootout
   ```

2. **Find issues that BLOCK this one:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:open blocking:#<number>"
   ```

3. **Find issues BLOCKED BY this one:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:open blocked-by:#<number>"
   ```

## Output Format

```
Issue #357: Add audio waveform visualization
Status: Open (BLOCKED)

Blocked by (must complete first):
  #355 - Set up FFmpeg audio processing [in_progress]
  #356 - Create waveform component [open]

Blocks (waiting on this):
  #360 - Implement A/B comparison view [open]

Dependency chain:
  #355 (in_progress) → #356 (open) → #357 (this) → #360

Recommendation: Focus on #355 first to unblock this work.
```
