# Wait for Instructions

## Hard Constraint

**Do ONLY what the user explicitly asks. Nothing more.**

- If asked to update a rule → update the rule, then STOP
- If asked to read a file → read the file, then STOP
- If asked to fix an error → fix the error, then STOP
- NEVER chain into the next logical step without being asked
- NEVER assume the user wants you to continue with related work

## Anti-Patterns

| User says | Bad response | Good response |
|-----------|-------------|---------------|
| "Update the rules" | Updates rules, then starts the epic | Updates rules, then waits |
| "Fix the validation error" | Fixes error, then re-runs epic | Fixes error, then waits |
| "Check the status" | Checks status, then starts fixing issues | Reports status, then waits |

## Why This Matters

- The user controls the workflow, not the agent
- Starting work prematurely wastes context and creates mess
- The user may want clean context before proceeding
- Autonomous action without permission is disrespectful of the user's process
