#!/usr/bin/env -S python3 -u
"""
Plan an epic by orchestrating specialised agents through a 7-step pipeline.

Pipeline:
  1. epic-context-loader    → CONTEXT.md
  2. epic-gray-area-analyst → questions printed to terminal
  3. [interactive pause]    → user answers → appended to CONTEXT.md
  4. epic-goal-backward     → GOALS.md
  5. epic-task-breakdown    → TASKS.md
  6. plan-reviewer          → REVIEW.md (gate: APPROVE or REVISE)
  7. tasks_from_plan.py     → .tasks/ files + created.json (local, no GH issues)

Usage:
    python scripts/plan_epic.py 33
    python scripts/plan_epic.py 33 --skip-gray-areas
    python scripts/plan_epic.py 33 --dry-run
    python scripts/plan_epic.py 33 --from-step 4

Or via just:
    just plan 33
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
RUN_EPIC = PROJECT_ROOT / "scripts" / "run_epic.py"

REPO = "krazyuniks/guitar-tone-shootout"
TASKS_FROM_PLAN = PROJECT_ROOT / "scripts" / "tasks_from_plan.py"

# Steps in the pipeline
STEPS = {
    1: "epic-context-loader",
    2: "epic-gray-area-analyst",
    3: "interactive-pause",
    4: "epic-goal-backward",
    5: "epic-task-breakdown",
    6: "plan-reviewer",
    7: "task-materialisation",
}

MAX_REVIEW_RETRIES = 1  # re-run task-breakdown once if REVISE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def die(msg: str) -> None:
    """Print error and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def slugify(title: str) -> str:
    """Convert issue title to a filesystem-safe slug."""
    # Remove common prefixes
    title = re.sub(r"^\[Epic\]:?\s*", "", title, flags=re.IGNORECASE)
    # Lowercase, replace non-alphanum with hyphens, collapse
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    # Truncate to reasonable length
    return slug[:60].rstrip("-")


def get_epic(epic_number: int) -> dict:
    """Fetch epic from GitHub."""
    result = subprocess.run(
        [
            "gh", "issue", "view", str(epic_number),
            "--repo", REPO,
            "--json", "title,body,labels,state",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        die(f"Failed to fetch issue #{epic_number}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def dispatch_agent(
    agent_name: str,
    prompt: str,
    *,
    dry_run: bool = False,
    max_turns: int = 20,
) -> subprocess.CompletedProcess | None:
    """Dispatch an agent via run_epic.py dispatch."""
    if dry_run:
        print(f"  [dry-run] Would dispatch '{agent_name}' (max_turns={max_turns})")
        print(f"  [dry-run] Prompt preview ({len(prompt)} chars):")
        # Show first 500 chars of prompt
        preview = prompt[:500]
        if len(prompt) > 500:
            preview += "\n  ... (truncated)"
        for line in preview.splitlines():
            print(f"    {line}")
        return None

    print(f"  Dispatching '{agent_name}'...")
    result = subprocess.run(
        [
            sys.executable, str(RUN_EPIC),
            "dispatch", agent_name,
            "--max-turns", str(max_turns),
            prompt,
        ],
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        die(f"Agent '{agent_name}' failed (exit {result.returncode})")
    return result


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def step_setup(epic_number: int) -> tuple[dict, str, Path]:
    """Step 0: Fetch epic, derive slug, create planning dir, write EPIC.md.

    Returns (epic, slug, epic_dir).
    """
    print(f"=== Setup: Fetching epic #{epic_number} ===")
    epic = get_epic(epic_number)
    slug = slugify(epic["title"])
    epic_dir = PLANNING_DIR / slug

    print(f"  Title: {epic['title']}")
    print(f"  Slug: {slug}")
    print(f"  Dir: {epic_dir}")

    epic_dir.mkdir(parents=True, exist_ok=True)

    # Write epic body for agents to reference
    epic_md = epic_dir / "EPIC.md"
    epic_md.write_text(
        f"# Epic #{epic_number}: {epic['title']}\n\n{epic.get('body', '')}\n"
    )
    print(f"  Wrote: {epic_md.relative_to(PROJECT_ROOT)}")
    print()

    return epic, slug, epic_dir


def step_1_context_loader(
    slug: str, epic_number: int, epic: dict, *, dry_run: bool = False
) -> None:
    """Step 1: Load project context into CONTEXT.md."""
    print("=== Step 1: Context Loader ===")

    prompt = (
        f"slug: {slug}\n"
        f"issue_number: {epic_number}\n"
        f"feature_description: {epic['title']}\n\n"
        f"Epic body:\n{epic.get('body', '(no body)')}"
    )
    dispatch_agent("epic-context-loader", prompt, dry_run=dry_run)
    print()


def step_2_gray_area_analyst(
    slug: str, epic: dict, *, dry_run: bool = False
) -> None:
    """Step 2: Detect gray areas and print questions."""
    print("=== Step 2: Gray Area Analyst ===")

    prompt = (
        f"feature_description: {epic['title']}\n\n"
        f"Epic body:\n{epic.get('body', '(no body)')}"
    )
    dispatch_agent("epic-gray-area-analyst", prompt, dry_run=dry_run)
    print()


def step_3_interactive_pause(slug: str, epic_dir: Path, *, dry_run: bool = False) -> None:
    """Step 3: Collect user answers and append to CONTEXT.md."""
    print("=== Step 3: Interactive Pause ===")

    if dry_run:
        print("  [dry-run] Would pause for user input")
        print()
        return

    print()
    print("  Review the questions above and provide your decisions.")
    print("  Type your answers below (multi-line). Press Ctrl+D when done.")
    print("  (Or press Ctrl+C to abort)")
    print()

    try:
        lines: list[str] = []
        while True:
            try:
                line = input("  > ")
                lines.append(line)
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)

    answers = "\n".join(lines).strip()
    if not answers:
        print("  No answers provided. Continuing without locked decisions.")
        print()
        return

    # Append locked decisions to CONTEXT.md
    context_path = epic_dir / "CONTEXT.md"
    if context_path.exists():
        existing = context_path.read_text()
        # Replace the placeholder section or append
        if "## Locked Decisions" in existing:
            # Replace the section content
            parts = existing.split("## Locked Decisions", 1)
            updated = (
                parts[0]
                + "## Locked Decisions\n\n"
                + answers
                + "\n"
            )
            context_path.write_text(updated)
        else:
            with context_path.open("a") as f:
                f.write(f"\n## Locked Decisions\n\n{answers}\n")
    else:
        context_path.write_text(f"## Locked Decisions\n\n{answers}\n")

    print()
    print(f"  Appended locked decisions to {context_path.relative_to(PROJECT_ROOT)}")
    print()


def step_4_goal_backward(slug: str, *, dry_run: bool = False) -> None:
    """Step 4: Goal-backward analysis → GOALS.md."""
    print("=== Step 4: Goal-Backward Analysis ===")

    prompt = f"slug: {slug}\nlocked_decisions: (see CONTEXT.md)"
    dispatch_agent("epic-goal-backward", prompt, dry_run=dry_run)
    print()


def step_5_task_breakdown(
    slug: str, *, dry_run: bool = False, review_feedback: str | None = None
) -> None:
    """Step 5: Task breakdown → TASKS.md."""
    print("=== Step 5: Task Breakdown ===")

    prompt = f"slug: {slug}"
    if review_feedback:
        prompt += (
            f"\n\n## Review Feedback (from plan-reviewer)\n\n"
            f"The previous TASKS.md was rejected. Fix the following issues:\n\n"
            f"{review_feedback}"
        )
    dispatch_agent("epic-task-breakdown", prompt, dry_run=dry_run)
    print()


def step_6_plan_review(slug: str, epic_dir: Path, *, dry_run: bool = False) -> str:
    """Step 6: Plan review gate → REVIEW.md. Returns verdict."""
    print("=== Step 6: Plan Review ===")

    prompt = f"slug: {slug}"
    dispatch_agent("plan-reviewer", prompt, dry_run=dry_run)

    if dry_run:
        print("  [dry-run] Would check verdict in REVIEW.md")
        print()
        return "APPROVE"

    # Parse verdict from REVIEW.md
    review_path = epic_dir / "REVIEW.md"
    if not review_path.exists():
        die("plan-reviewer did not create REVIEW.md")

    review_content = review_path.read_text()

    # Look for **Verdict:** APPROVE or REVISE
    verdict_match = re.search(
        r"\*\*Verdict:\*\*\s*(APPROVE|REVISE)", review_content
    )
    if not verdict_match:
        # Try without bold markers
        verdict_match = re.search(
            r"Verdict:\s*(APPROVE|REVISE)", review_content, re.IGNORECASE
        )

    if not verdict_match:
        print("  WARNING: Could not parse verdict from REVIEW.md, defaulting to APPROVE")
        verdict = "APPROVE"
    else:
        verdict = verdict_match.group(1).upper()

    print(f"  Verdict: {verdict}")
    print()
    return verdict


def step_6_review_gate(slug: str, epic_dir: Path, *, dry_run: bool = False) -> None:
    """Step 6: Plan review with retry loop."""
    verdict = step_6_plan_review(slug, epic_dir, dry_run=dry_run)

    if verdict == "APPROVE":
        return

    # REVISE: extract feedback and retry task-breakdown
    review_path = epic_dir / "REVIEW.md"
    review_content = review_path.read_text() if review_path.exists() else ""

    # Extract the Issues Found section as feedback
    feedback = review_content
    issues_match = re.search(
        r"## Issues Found\s*\n(.*?)(?=\n## |\Z)",
        review_content,
        re.DOTALL,
    )
    if issues_match:
        feedback = issues_match.group(1).strip()

    print("  Re-running task breakdown with review feedback...")
    print()

    # Retry: re-run step 5 with feedback, then re-review
    step_5_task_breakdown(slug, dry_run=dry_run, review_feedback=feedback)
    verdict = step_6_plan_review(slug, epic_dir, dry_run=dry_run)

    if verdict == "APPROVE":
        return

    # Still REVISE after retry — halt for human
    print()
    print("=" * 60)
    print("PLAN REVIEW FAILED — Requires human intervention")
    print("=" * 60)
    print()
    print(f"Review: {review_path.relative_to(PROJECT_ROOT)}")
    print()
    # Print the review content for the human
    if review_path.exists():
        content = review_path.read_text()
        for line in content.splitlines()[:50]:
            print(f"  {line}")
    print()
    die("Plan review rejected after retry. Fix issues manually and re-run with --from-step 5")


def step_7_materialise_tasks(
    slug: str, epic: dict, epic_number: int, epic_dir: Path, *, dry_run: bool = False
) -> None:
    """Step 7: Materialise tasks locally and update epic GH issue."""
    print("=== Step 7: Task Materialisation (local) ===")

    tasks_md = epic_dir / "TASKS.md"
    if not tasks_md.exists():
        die(f"TASKS.md not found at {tasks_md}")

    # 1. Run tasks_from_plan.py to write .tasks/ files
    cmd = [sys.executable, str(TASKS_FROM_PLAN), str(tasks_md), str(epic_number)]
    if dry_run:
        cmd.append("--dry-run")

    print(f"  Running: tasks_from_plan.py ...")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        die("tasks_from_plan.py failed")

    # 2. Update the epic GH issue body with a task summary
    created_path = epic_dir / "created.json"
    if not dry_run and created_path.exists():
        created = json.loads(created_path.read_text())
        task_lines = []
        for t in created.get("tasks", []):
            local_id = t["local_id"]
            plan_id = t["id"]
            title = t["title"]
            task_lines.append(f"- [ ] T{local_id}: {plan_id} - {title}")

        task_summary = "\n".join(task_lines)
        body_update = (
            f"## Tasks\n\n"
            f"{task_summary}\n\n"
            f"---\n"
            f"*Tasks are local (.tasks/E{epic_number}/). "
            f"Run `just epic-start {epic_number}` to begin TDD execution.*"
        )

        # Read current epic body and append/replace Tasks section
        current_body = epic.get("body", "")
        if "## Tasks" in current_body:
            # Replace existing Tasks section
            new_body = re.sub(
                r"## Tasks\s*\n.*?(?=\n## |\Z)",
                body_update,
                current_body,
                flags=re.DOTALL,
            )
        else:
            new_body = current_body.rstrip() + "\n\n" + body_update

        # Write updated body to temp file and apply
        body_file = epic_dir / "epic-body-updated.md"
        body_file.write_text(new_body)

        print(f"  Updating epic #{epic_number} on GitHub...")
        gh_result = subprocess.run(
            [
                "gh", "issue", "edit", str(epic_number),
                "--repo", REPO,
                "--body-file", str(body_file),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if gh_result.returncode != 0:
            print(f"  WARNING: Failed to update epic body: {gh_result.stderr.strip()}")
            print("  (Tasks were still written locally — GH update can be retried)")
        else:
            print(f"  Updated epic #{epic_number} body with task summary")
    elif dry_run:
        print("  [dry-run] Would update epic body on GitHub with task summary")

    print()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    epic_number: int,
    *,
    skip_gray_areas: bool = False,
    dry_run: bool = False,
    from_step: int = 1,
) -> None:
    """Run the full planning pipeline."""

    # Step 0: Setup (always runs)
    epic, slug, epic_dir = step_setup(epic_number)

    # Check if resuming from a later step
    if from_step > 1:
        print(f"Resuming from step {from_step}: {STEPS[from_step]}")
        print()

        # Verify earlier artifacts exist
        required: dict[int, str] = {
            2: "CONTEXT.md",
            3: "CONTEXT.md",
            4: "CONTEXT.md",
            5: "GOALS.md",
            6: "TASKS.md",
            7: "TASKS.md",
        }
        if from_step in required:
            artifact = epic_dir / required[from_step]
            if not artifact.exists():
                die(
                    f"Cannot resume from step {from_step}: "
                    f"{artifact.relative_to(PROJECT_ROOT)} not found.\n"
                    f"Run earlier steps first."
                )

    # Step 1: Context loader
    if from_step <= 1:
        step_1_context_loader(slug, epic_number, epic, dry_run=dry_run)

    # Steps 2-3: Gray area analysis (skippable)
    if not skip_gray_areas:
        if from_step <= 2:
            step_2_gray_area_analyst(slug, epic, dry_run=dry_run)
        if from_step <= 3:
            step_3_interactive_pause(slug, epic_dir, dry_run=dry_run)
    else:
        if from_step <= 3:
            print("=== Steps 2-3: Skipped (--skip-gray-areas) ===")
            print()

    # Step 4: Goal-backward analysis
    if from_step <= 4:
        step_4_goal_backward(slug, dry_run=dry_run)

    # Step 5: Task breakdown
    if from_step <= 5:
        step_5_task_breakdown(slug, dry_run=dry_run)

    # Step 6: Plan review gate
    if from_step <= 6:
        step_6_review_gate(slug, epic_dir, dry_run=dry_run)

    # Step 7: Task materialisation (local, no GH issues)
    if from_step <= 7:
        step_7_materialise_tasks(slug, epic, epic_number, epic_dir, dry_run=dry_run)

    # Done
    print("=" * 60)
    print(f"Planning complete for epic #{epic_number}!")
    print("=" * 60)
    print()
    print("Artifacts:")
    for f in sorted(epic_dir.iterdir()):
        if f.is_file():
            print(f"  {f.relative_to(PROJECT_ROOT)}")
    print()
    print("Next steps:")
    print(f"  just epic-status {epic_number} # Check status")
    print(f"  just epic-start {epic_number}  # Begin TDD execution")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan an epic through the full agent pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/plan_epic.py 33                    # Full pipeline\n"
            "  python scripts/plan_epic.py 33 --skip-gray-areas  # Skip interactive Q&A\n"
            "  python scripts/plan_epic.py 33 --dry-run          # Show prompts only\n"
            "  python scripts/plan_epic.py 33 --from-step 4      # Resume from step 4\n"
        ),
    )
    parser.add_argument("epic", type=int, help="Epic issue number")
    parser.add_argument(
        "--skip-gray-areas",
        action="store_true",
        help="Skip steps 2-3 (gray area analysis + interactive pause)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompts without dispatching agents",
    )
    parser.add_argument(
        "--from-step",
        type=int,
        choices=range(1, 8),
        default=1,
        metavar="N",
        help="Resume from step N (1-7, requires earlier artifacts)",
    )

    args = parser.parse_args()

    run_pipeline(
        args.epic,
        skip_gray_areas=args.skip_gray_areas,
        dry_run=args.dry_run,
        from_step=args.from_step,
    )


if __name__ == "__main__":
    main()
