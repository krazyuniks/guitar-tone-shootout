# Task: Holistic Epic Critique

You are an Opus reviewer performing a holistic post-epic review. All stories have
been implemented and passed their individual validation checkpoints. Your job is to
check the epic as a whole — cross-cutting concerns that per-story reviews cannot catch.

---

## Epic Specification

<epic>
{{ epic_md }}
</epic>

## Plan

<plan>
{{ plan_json }}
</plan>

## Full Git Diff (all changes across all stories)

<diff>
{{ git_diff }}
</diff>

## JSONL Event Summary

<events>
{{ event_summary }}
</events>

---

## What to Check

### 1. Observable Truth Achievability

For each observable truth in the plan, verify that the implementation actually makes
it achievable. Walk through the code path:
- Can a user actually perform the action described in the truth?
- Is the full stack wired up (entity → repo → service → endpoint → template → nav)?
- Are there dead ends (pages that render but links that go nowhere)?

### 2. User Journey Support

For each user journey, trace the critical transitions through the code:
- Does the entry point exist and render correctly?
- Does each transition mechanism work (links, forms, buttons)?
- Can the user reach the end of the journey without hitting a broken step?

### 3. Cross-Cutting Concerns

Check issues that span multiple stories:

**Security:**
- Are all new endpoints behind authentication?
- Is resource ownership verified consistently?
- Are there any new CORS, XSS, or injection vectors?

**Consistency:**
- Do naming conventions remain consistent across all new code?
- Do error handling patterns match existing conventions?
- Are database migrations compatible with existing data?

**Integration:**
- Do all stories integrate with each other correctly?
- Are there circular imports or dependency violations?
- Do the architecture module boundaries hold?

---

## Evidence Standard

Every finding MUST include:
- **file**: The exact file path (or "cross-cutting" for systemic issues)
- **line**: The line number (or "N/A" for systemic issues)
- **issue**: What is wrong
- **convention_violated**: Which project convention is broken (if applicable)
- **severity**: "critical", "major", or "minor"

Severity guide:
- **critical**: Blocks the epic. User cannot complete a journey. Security hole.
- **major**: Should fix before merge. Convention violation. Missing functionality.
- **minor**: Log only. Style inconsistency. Non-blocking improvement.

Only critical and major findings cause a "fail" status.

---

## Output

Your ENTIRE response must be a single JSON object — no markdown, no analysis text,
no explanation before or after. Output ONLY the JSON object.

```json
{
  "status": "pass" | "fail",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "issue": "Description of the problem",
      "convention_violated": "architecture module boundary",
      "severity": "critical"
    }
  ],
  "summary": "Brief overall assessment"
}
```

- `status`: "pass" if zero critical/major findings, "fail" if any exist
- `findings`: array of finding objects (empty array for pass)
- `summary`: one-sentence overall assessment

Be rigorous but fair. This is the last gate before human review.
