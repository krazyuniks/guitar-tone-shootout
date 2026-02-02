# No Workarounds Rule

## Critical Rule

**NEVER implement workarounds, stopgaps, or deviations from the plan.**

If you encounter a situation where the planned approach doesn't work:

1. **STOP immediately**
2. **Explain** what isn't working and why
3. **Ask** how to proceed properly
4. **Wait** for explicit direction

## What Constitutes a Workaround

- Creating files in locations different from the architecture (e.g., `public/templates/` instead of `src/pages/`)
- Adding copy scripts instead of fixing the build process
- Using different ports/endpoints than specified
- Implementing "temporary" solutions that bypass the proper pattern
- Partial implementations that defer work to "future issues"
- Any solution that requires manual steps not in the standard build

## Examples

**BAD - Workaround:**
> "The Astro endpoint pattern isn't working for all templates, so I'll put them in `public/templates/` and add a copy script."

**GOOD - Stop and ask:**
> "The Astro endpoint pattern works for `gear/detail.html.ts` but I'm having trouble with the other 37 templates because [specific reason]. Should I continue with this pattern, or is there a different approach you want?"

**BAD - Partial implementation:**
> "I've migrated 1 of 38 templates to the new pattern. The rest can be done in issue #510."

**GOOD - Complete or clarify scope:**
> "Migrating all 38 templates will take significant time. The scope says 'establish pattern' - should I do all 38, or just the gear templates for this issue?"

## Guessing

**NEVER guess** at:
- Architecture decisions
- File locations
- Build processes
- Port configurations
- API contracts

If something is unclear or undocumented, **ask**.

## Deferring Work

Do not create "Related: #XXX" references to defer incomplete work unless:
- The scope explicitly allows partial implementation
- You have confirmed with the user that deferral is acceptable
- The current work is fully functional without the deferred part

## When Plans Don't Match Reality

If the plan/issue specifies something that doesn't match the current codebase:
1. **Point out the discrepancy**
2. **Do not silently adapt** - the plan may need updating, or the codebase may be wrong
3. **Wait for clarification** before proceeding
