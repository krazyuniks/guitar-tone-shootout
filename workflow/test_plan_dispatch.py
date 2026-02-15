#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0",
# ]
# ///
"""Fast test for plan generation pipeline.

Usage:
    ./workflow/test_plan_dispatch.py              # parse last saved output (instant)
    ./workflow/test_plan_dispatch.py --dispatch    # dispatch tiny epic + parse (~30s)
    ./workflow/test_plan_dispatch.py --dry-run     # print prompt, no dispatch
"""

import sys
from pathlib import Path

current = Path(__file__).resolve().parent.parent
if str(current) not in sys.path:
    sys.path.insert(0, str(current))

from workflow.dispatch import AgentResult  # noqa: E402
from workflow.plan_generator import _parse_structured_plan  # noqa: E402

LOGS_DIR = current / ".planning" / "logs"
SAVED_OUTPUT = LOGS_DIR / "last-planner-output.txt"


def test_parse():
    """Parse the last saved planner output — instant, no dispatch."""
    if not SAVED_OUTPUT.exists():
        print(f"No saved output at {SAVED_OUTPUT}")
        print("Run with --dispatch first to generate one.")
        sys.exit(1)

    text = SAVED_OUTPUT.read_text(encoding="utf-8")
    print(f"Parsing saved output ({len(text)} chars)...")

    result = AgentResult(success=True, output=text)
    try:
        plan = _parse_structured_plan(result)
    except Exception as exc:
        print(f"\nPARSE FAILED: {exc}")
        sys.exit(1)

    print("\nParsed OK:")
    print(f"  Epic: #{plan.epic_number}")
    print(f"  Goal: {plan.goal[:80]}...")
    print(f"  Truths: {len(plan.observable_truths)}")
    print(f"  Journeys: {len(plan.user_journeys)}")
    print(f"  Stories: {len(plan.stories)}")
    print(f"  Checkpoints: {len(plan.validation_checkpoints)}")

    # Cross-reference checks (same as Phase A)
    truth_ids = {t.id for t in plan.observable_truths}
    addressed = set()
    for s in plan.stories:
        addressed.update(s.truths_addressed)
    missing = truth_ids - addressed
    if missing:
        print(f"\n  FAIL: truths not addressed by any story: {missing}")
        sys.exit(1)

    covered = set()
    for j in plan.user_journeys:
        covered.update(j.truths_covered)
    uncovered = truth_ids - covered
    if uncovered:
        print(f"\n  FAIL: truths not in any journey: {uncovered}")
        sys.exit(1)

    print("\n  All truths addressed and covered. PASS")


def dispatch_and_parse():
    """Dispatch a tiny epic and parse the result."""
    from workflow.dispatch import dispatch_with_fallback
    from workflow.plan_generator import _build_planner_prompt

    context = """\
# Epic Context
**Assembled:** 2026-01-01T00:00:00Z
**Detected Areas:** data_model, api_contract

## Epic Description
---
github_issue: 999
title: "Add Gear Tags"
state: OPEN
labels: ["epic"]
---
## Epic: Add Gear Tags
Add tagging to gear items so users can organise and filter their collection.
### Scope
- Tag entity, ORM model, repository, service
- API endpoint: GET/POST /api/v1/gear/{gear_id}/tags
- Gear detail page shows tags
- Gear list page can filter by tag
### Pre-requisites
Gear CRUD complete.
---
## Codebase Structure
apps/webapp/src/webapp/main.py — FastAPI app
apps/webapp/src/webapp/routes/ — route modules
libs/core/src/gts_core/gear/ — gear domain
apps/webapp/src/webapp/templates/ — Jinja2 templates
---
## Wiki Indexes Available
- GTS-Technical-Architecture.index
- Frontend-Architecture.index
"""

    prompt = _build_planner_prompt(context=context, epic_number=999)

    if "--dry-run" in sys.argv:
        print(prompt)
        print(f"\n--- {len(prompt)} chars, ~{len(prompt)//4} tokens ---")
        return

    print(f"Dispatching ({len(prompt)} chars, ~{len(prompt)//4} tokens)...")
    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model="sonnet",
        fallback_model="haiku",
        tools=[],
        max_turns=5,
        max_budget_usd=0.50,
        json_schema=None,
        cwd=current,
    )

    print(f"success={result.success}, turns={result.turns}, output={len(result.output)} chars")
    if not result.success:
        print(f"FAILED: {result.output[:500]}")
        sys.exit(1)

    # Save for future --parse runs
    SAVED_OUTPUT.write_text(result.output, encoding="utf-8")
    print(f"Saved to {SAVED_OUTPUT}")

    try:
        plan = _parse_structured_plan(result)
    except Exception as exc:
        print(f"\nPARSE FAILED: {exc}")
        sys.exit(1)

    print(f"\nSUCCESS: {len(plan.stories)} stories, {len(plan.observable_truths)} truths")


if __name__ == "__main__":
    if "--dispatch" in sys.argv or "--dry-run" in sys.argv:
        dispatch_and_parse()
    else:
        test_parse()
