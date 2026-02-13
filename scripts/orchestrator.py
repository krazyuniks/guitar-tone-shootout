"""V2 epic orchestrator -- outer loop + GitHub integration.

The main entry point for the V2 behavioural-validation epic workflow.
Provides three subcommands:

    python scripts/orchestrator.py plan <N> [--resume]
    python scripts/orchestrator.py run <N> [--resume]
    python scripts/orchestrator.py status <N>

The orchestrator is stateless: it reads the JSONL log, determines the
next step, builds a prompt, dispatches one agent, waits, and loops.
No AI tokens are spent on orchestration.

Reference: Research doc Section 2 (Crash Recovery), Section 8.3
Decisions 4, 5.
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.context_assembler import AssemblyError, assemble_context
from scripts.epic_ingest import IngestionError, ingest_epic
from scripts.git_helpers import (
    GitCommitError,
    GitConflictError,
    GitPushError,
    git_sync,
    robust_commit,
)
from scripts.jsonl_logger import (
    EventLogger,
    generate_run_id,
    get_resumable_state,
    is_story_complete,
    read_log,
)
from scripts.plan_generator import PlanGenerationError, generate_plan
from scripts.plan_verifier import (
    PlanVerificationError,
    present_decision_gate,
    verify_with_revision_cycle,
)
from scripts.story_executor import execute_story

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
GH_REPO = "krazyuniks/guitar-tone-shootout"


# ---------------------------------------------------------------------------
# GitHub integration helpers (Section 8.3 Decision 4)
# ---------------------------------------------------------------------------


def comment_on_epic(epic_number: int, body: str) -> str | None:
    """Post a comment on a GitHub epic issue.

    Args:
        epic_number: The GitHub issue number.
        body: Markdown body for the comment.

    Returns:
        The comment URL if successful, None on failure.
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(epic_number),
                "--repo",
                GH_REPO,
                "--body",
                body,
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        if result.returncode == 0:
            # gh issue comment prints the URL on success
            url = result.stdout.strip()
            logger.info("GitHub comment posted: %s", url)
            return url
        logger.warning("Failed to post GitHub comment: %s", result.stderr.strip())
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Failed to post GitHub comment: %s", exc)
        return None


def label_epic(epic_number: int, label: str) -> bool:
    """Add a label to a GitHub epic issue.

    Args:
        epic_number: The GitHub issue number.
        label: Label to add.

    Returns:
        True if successful.
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                str(epic_number),
                "--repo",
                GH_REPO,
                "--add-label",
                label,
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("Label '%s' added to epic #%d", label, epic_number)
            return True
        logger.warning("Failed to label epic: %s", result.stderr.strip())
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Failed to label epic: %s", exc)
        return False


# ---------------------------------------------------------------------------
# GitHub comment builders
# ---------------------------------------------------------------------------


def build_planning_complete_comment(plan: dict) -> str:
    """Build the 'Planning Complete' GitHub comment.

    Posted when the planning pipeline completes and the plan is approved.

    Args:
        plan: The plan.json dict.

    Returns:
        Markdown-formatted comment body.
    """
    stories = plan.get("stories", [])
    checkpoints = plan.get("validation_checkpoints", [])
    goal = plan.get("goal", "")

    story_lines = []
    for i, story in enumerate(stories, 1):
        model = story.get("agent", {}).get("model", "sonnet")
        budget = story.get("agent", {}).get("max_budget_usd", 0)
        story_lines.append(f"| {i} | {story.get('name', '?')} | {model} | ${budget:.2f} |")

    return f"""\
## Planning Complete

**Goal:** {goal}

### Story Sequence

| # | Story | Model | Budget |
|---|-------|-------|--------|
{chr(10).join(story_lines)}

**Validation checkpoints:** {len(checkpoints)}
**Total stories:** {len(stories)}
"""


def build_story_comment(story: dict, events: list[dict]) -> str:
    """Build the 'Story Complete' GitHub comment.

    Posted after each story passes its validation checkpoint.

    Args:
        story: The story dict from plan.json.
        events: All JSONL events so far.

    Returns:
        Markdown-formatted comment body.
    """
    story_id = story.get("story_id", "?")
    name = story.get("name", "?")
    model = story.get("agent", {}).get("model", "sonnet")

    # Find the most recent agent_complete for this story
    agent_event = None
    for e in reversed(events):
        if e.get("event") == "agent_complete" and e.get("story_id") == story_id:
            agent_event = e
            break

    turns = agent_event.get("turns", "?") if agent_event else "?"
    cost = agent_event.get("cost_usd") if agent_event else None
    commit = agent_event.get("commit", "?") if agent_event else "?"
    cost_str = f"${cost:.2f}" if cost is not None else "?"

    # Count files from scope
    scope = story.get("scope", {})
    created = len(scope.get("create", []))
    modified = len(scope.get("modify", []))

    # Find validation results
    validation_lines = []
    for e in reversed(events):
        if (
            e.get("event") in ("validation_pass", "validation_fail")
            and e.get("story_id") == story_id
        ):
            for r in e.get("results", []):
                status_icon = "PASS" if r.get("status") == "pass" else "FAIL"
                validation_lines.append(f"- [{status_icon}] {r.get('criterion', '?')}")
            break

    validation_section = (
        "\n".join(validation_lines) if validation_lines else "No validation checkpoint"
    )

    return f"""\
## Story Complete: {name}

**Agent:** {story_id} | **Model:** {model} | **Turns:** {turns} | **Cost:** {cost_str}
**Files:** {created} created, {modified} modified | **Commit:** {commit}

### Validation
{validation_section}
"""


def build_failure_comment(story: dict, events: list[dict]) -> str:
    """Build the 'Story Failed' GitHub comment.

    Posted when a story fails after exhausting retries.

    Args:
        story: The story dict from plan.json.
        events: All JSONL events so far.

    Returns:
        Markdown-formatted comment body.
    """
    story_id = story.get("story_id", "?")
    name = story.get("name", "?")

    # Find the latest failure event
    failure_event = None
    for e in reversed(events):
        if e.get("story_id") == story_id and e.get("event") in (
            "story_failed",
            "exit_to_human",
            "agent_failed",
            "validation_fail",
        ):
            failure_event = e
            break

    reason = "Unknown"
    category = "unknown"
    if failure_event:
        reason = failure_event.get("reason", failure_event.get("failure_reason", "Unknown"))
        category = failure_event.get("failure_category", "unknown")

    return f"""\
## Story Failed: {name}

**Story:** {story_id}
**Failure category:** {category}
**Reason:** {reason}

Manual intervention required. Check the JSONL log for full details.
"""


def build_completion_comment(plan: dict, events: list[dict]) -> str:
    """Build the 'Epic Complete' GitHub comment.

    Posted when all stories complete successfully.

    Args:
        plan: The plan.json dict.
        events: All JSONL events.

    Returns:
        Markdown-formatted comment body.
    """
    stories = plan.get("stories", [])
    completed_ids = {e["story_id"] for e in events if e.get("event") == "story_complete"}

    # Total cost
    total_cost = sum(
        e.get("cost_usd", 0) or 0 for e in events if e.get("event") == "agent_complete"
    )

    # Commits
    commits = [
        e.get("commit", "?")
        for e in events
        if e.get("event") == "story_complete" and e.get("commit")
    ]

    return f"""\
## Epic Complete

**Stories completed:** {len(completed_ids)}/{len(stories)}
**Total cost:** ${total_cost:.2f}
**Commits:** {', '.join(commits)}

All stories passed their validation checkpoints. Please verify the results and close this issue when satisfied.
"""


def build_human_validation_comment(plan: dict) -> str:
    """Build the 'Human Validation Prompt' comment.

    Posted as the final comment after epic completion.

    Args:
        plan: The plan.json dict.

    Returns:
        Markdown-formatted comment body.
    """
    truths = plan.get("observable_truths", [])
    journeys = plan.get("user_journeys", [])

    truth_lines = [f"- [ ] {t.get('statement', '?')}" for t in truths]
    journey_lines = []
    for j in journeys:
        journey_lines.append(f"### {j.get('journey_id', '?')}: {j.get('persona', '?')}")
        journey_lines.append(j.get("narrative", ""))
        journey_lines.append("")

    return f"""\
## Human Validation Required

All stories passed automated validation. Please manually verify the following observable truths:

{chr(10).join(truth_lines)}

### User Journeys to Walk

{chr(10).join(journey_lines)}

When satisfied, close this issue.
"""


# ---------------------------------------------------------------------------
# SUMMARY.md generation (Section 8.3 -- deterministic, $0)
# ---------------------------------------------------------------------------


def generate_summary(epic_dir: Path, plan: dict, events: list[dict]) -> Path:
    """Generate SUMMARY.md from JSONL logs.

    A deterministic Python function ($0 AI cost) that reads the JSONL
    and renders markdown. It runs as the final step of both run_epic()
    and the failure exit path.

    Args:
        epic_dir: Path to the epic directory.
        plan: The plan.json dict.
        events: All JSONL events (epic + story level combined).

    Returns:
        Path to the generated SUMMARY.md.
    """
    stories = plan.get("stories", [])
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Stories completed
    completed_ids = sorted({e["story_id"] for e in events if e.get("event") == "story_complete"})
    # Stories failed
    failed_ids = sorted({e["story_id"] for e in events if e.get("event") == "story_failed"})
    # Exit to human events
    exit_events = [e for e in events if e.get("event") == "exit_to_human"]

    # Total cost
    total_cost = sum(
        e.get("cost_usd", 0) or 0 for e in events if e.get("event") == "agent_complete"
    )

    # Commits
    commits = [
        e.get("commit", "?")
        for e in events
        if e.get("event") == "story_complete" and e.get("commit")
    ]

    # Validation checkpoint results
    validation_results = []
    for e in events:
        if e.get("event") in ("validation_pass", "validation_fail"):
            status = "PASS" if e["event"] == "validation_pass" else "FAIL"
            story_id = e.get("story_id", "?")
            check_type = e.get("check_type", "?")
            criteria_count = len(e.get("results", []))
            validation_results.append(
                f"| {story_id} | {check_type} | {status} | {criteria_count} |"
            )

    # Failure details
    failure_lines = []
    for sid in failed_ids:
        # Find the failure reason
        for e in reversed(events):
            if e.get("story_id") == sid and e.get("event") == "story_failed":
                reason = e.get("reason", "Unknown")
                failure_lines.append(f"- **{sid}**: {reason}")
                break

    # Deferred/unresolved items
    deferred_lines = []
    for e in exit_events:
        story_id = e.get("story_id", "?")
        reason = e.get("reason", "Unknown")
        deferred_lines.append(f"- **{story_id}**: {reason}")

    lines = [
        "# Epic Summary",
        "",
        f"**Generated:** {now}",
        "",
        "## Stories",
        "",
        f"- **Completed:** {len(completed_ids)}/{len(stories)} ({', '.join(completed_ids) if completed_ids else 'none'})",
        f"- **Failed:** {len(failed_ids)} ({', '.join(failed_ids) if failed_ids else 'none'})",
        "",
        "## Cost",
        "",
        f"- **Total:** ${total_cost:.2f}",
        "",
        "## Commits",
        "",
    ]
    if commits:
        for c in commits:
            lines.append(f"- `{c}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Validation Checkpoints",
            "",
            "| Story | Check Type | Status | Criteria |",
            "|-------|-----------|--------|----------|",
        ]
    )
    if validation_results:
        lines.extend(validation_results)
    else:
        lines.append("| - | - | - | - |")

    if failure_lines:
        lines.extend(
            [
                "",
                "## Failures",
                "",
            ]
        )
        lines.extend(failure_lines)

    if deferred_lines:
        lines.extend(
            [
                "",
                "## Deferred/Unresolved",
                "",
            ]
        )
        lines.extend(deferred_lines)

    content = "\n".join(lines) + "\n"
    summary_path = epic_dir / "SUMMARY.md"
    summary_path.write_text(content, encoding="utf-8")

    logger.info("SUMMARY.md generated at %s", summary_path)
    return summary_path


# ---------------------------------------------------------------------------
# Epic execution: the outer loop (Section 2)
# ---------------------------------------------------------------------------


def _load_plan(epic_dir: Path) -> dict:
    """Load plan.json from the epic directory."""
    plan_path = epic_dir / "plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(f"plan.json not found at {plan_path}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _collect_story_events(epic_dir: Path, plan: dict) -> list[dict]:
    """Collect all JSONL events from both epic and story logs.

    Reads the epic-level log and each story-level log, merging them
    into a single chronological list.

    Args:
        epic_dir: Path to the epic directory.
        plan: The plan.json dict (for story IDs).

    Returns:
        Combined list of all events sorted by timestamp.
    """
    all_events: list[dict] = []

    # Epic-level log
    epic_log = epic_dir / "epic.jsonl"
    all_events.extend(read_log(epic_log))

    # Story-level logs
    for story in plan.get("stories", []):
        story_id = story.get("story_id", "")
        story_log = epic_dir / "stories" / story_id / "story.jsonl"
        all_events.extend(read_log(story_log))

    # Sort by timestamp for chronological order
    all_events.sort(key=lambda e: e.get("ts", ""))
    return all_events


def _determine_next_story(
    plan: dict,
    completed_stories: list[str],
) -> dict | None:
    """Determine the next story to execute.

    Walks the plan's story list in order and returns the first story
    whose story_id is not in the completed set.

    Args:
        plan: The plan.json dict.
        completed_stories: List of completed story IDs.

    Returns:
        The next story dict, or None if all stories are complete.
    """
    for story in plan.get("stories", []):
        if story.get("story_id") not in completed_stories:
            return story
    return None


def _is_exit_to_human(events: list[dict], run_id: str) -> bool:
    """Check if the latest event for this run is an exit_to_human."""
    for event in reversed(events):
        if event.get("run_id") == run_id:
            return event.get("event") == "exit_to_human"
    return False


def run_epic(epic_number: int, resume: bool = False) -> None:
    """Execute all stories in an epic sequentially.

    The stateless outer loop: read log -> determine next story ->
    dispatch agent -> wait -> loop. No AI tokens spent on orchestration.

    On fresh start: generates a new run_id, logs epic_started.
    On resume: reuses the existing run_id, skips completed stories.

    Args:
        epic_number: The GitHub issue number of the epic.
        resume: If True, resume from the last completed event.
    """
    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        logger.error("Epic directory not found: %s", epic_dir)
        sys.exit(1)

    plan = _load_plan(epic_dir)
    stories = plan.get("stories", [])
    if not stories:
        logger.error("No stories found in plan.json for epic #%d", epic_number)
        sys.exit(1)

    epic_log_path = epic_dir / "epic.jsonl"
    events = read_log(epic_log_path)

    # Determine run_id: resume reuses existing, fresh start generates new
    if resume and events:
        # Find the latest run_id
        run_id = events[-1].get("run_id", "")
        if not run_id:
            logger.error("Cannot resume: no run_id found in epic.jsonl")
            sys.exit(1)

        state = get_resumable_state(events, run_id)
        completed_stories = state["completed_stories"]

        if state["next_action"] == "epic_complete":
            logger.info("Epic #%d already complete (run_id=%s)", epic_number, run_id)
            return

        if state["next_action"] == "exit_to_human":
            logger.info(
                "Epic #%d previously exited to human (run_id=%s, story=%s)",
                epic_number,
                run_id,
                state.get("failed_story_id", "?"),
            )
            return

        logger.info(
            "Resuming epic #%d (run_id=%s, completed=%d/%d)",
            epic_number,
            run_id,
            len(completed_stories),
            len(stories),
        )
    else:
        run_id = generate_run_id()
        completed_stories = []
        logger.info(
            "Starting epic #%d (run_id=%s, stories=%d)",
            epic_number,
            run_id,
            len(stories),
        )

    # Create the epic-level JSONL logger
    epic_logger = EventLogger(epic_log_path, run_id)

    # Log epic_started if this is a fresh start (not resume)
    if not resume or not events:
        epic_logger.log_event(
            "epic_started",
            epic=epic_number,
            stories=len(stories),
        )

    # The outer loop
    while True:
        # Re-read the log to get latest state (events accumulate)
        events = read_log(epic_log_path)

        # Check for exit_to_human
        if _is_exit_to_human(events, run_id):
            logger.info("Exiting to human (exit_to_human event found)")
            break

        # Refresh completed stories from the log
        completed_stories = sorted(
            {
                e["story_id"]
                for e in events
                if e.get("event") == "story_complete" and e.get("run_id") == run_id
            }
        )

        # Determine next story
        next_story = _determine_next_story(plan, completed_stories)
        if next_story is None:
            # All stories complete
            logger.info("All stories complete for epic #%d", epic_number)

            # Log epic_complete
            all_events = _collect_story_events(epic_dir, plan)
            total_cost = sum(
                e.get("cost_usd", 0) or 0 for e in all_events if e.get("event") == "agent_complete"
            )
            epic_logger.log_event(
                "epic_complete",
                epic=epic_number,
                stories_completed=len(completed_stories),
                total_cost_usd=total_cost,
            )

            # Post completion comment
            all_events = _collect_story_events(epic_dir, plan)
            comment_body = build_completion_comment(plan, all_events)
            url = comment_on_epic(epic_number, comment_body)
            if url:
                epic_logger.log_event(
                    "github_comment",
                    epic=epic_number,
                    comment_url=url,
                )

            # Post human validation prompt
            human_body = build_human_validation_comment(plan)
            url = comment_on_epic(epic_number, human_body)
            if url:
                epic_logger.log_event(
                    "github_comment",
                    epic=epic_number,
                    comment_url=url,
                )

            # Add label but do NOT close the epic
            label_epic(epic_number, "workflow-complete")

            # Generate SUMMARY.md
            all_events = _collect_story_events(epic_dir, plan)
            generate_summary(epic_dir, plan, all_events)

            break

        story_id = next_story.get("story_id", "unknown")

        # Idempotency check: skip if already complete in this run
        if is_story_complete(events, story_id, run_id):
            logger.info("Skipping completed story: %s", story_id)
            continue

        # Create story-level JSONL logger
        story_dir = epic_dir / "stories" / story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        story_log_path = story_dir / "story.jsonl"
        story_logger = EventLogger(story_log_path, run_id)

        # Execute the story
        success = execute_story(
            story=next_story,
            plan=plan,
            epic_dir=epic_dir,
            event_logger=story_logger,
            completed_stories=completed_stories,
        )

        # Re-read all events for comment building
        all_events = _collect_story_events(epic_dir, plan)

        if success:
            # Also log story_complete to the epic-level log
            epic_logger.log_event(
                "story_complete",
                story_id=story_id,
                attempt=_get_last_attempt(all_events, story_id),
                commit=_get_last_commit(all_events, story_id),
            )

            # Post story completion comment
            comment_body = build_story_comment(next_story, all_events)
            url = comment_on_epic(epic_number, comment_body)
            if url:
                epic_logger.log_event(
                    "github_comment",
                    epic=epic_number,
                    comment_url=url,
                )

            # Sync to remote after each successful story
            try:
                git_sync()
            except (GitConflictError, GitPushError) as exc:
                logger.warning("Git sync failed after story '%s': %s", story_id, exc)
        else:
            # Story failed -- post failure comment and exit
            comment_body = build_failure_comment(next_story, all_events)
            url = comment_on_epic(epic_number, comment_body)
            if url:
                epic_logger.log_event(
                    "github_comment",
                    epic=epic_number,
                    comment_url=url,
                )

            # Generate SUMMARY.md even on failure
            generate_summary(epic_dir, plan, all_events)
            break


# ---------------------------------------------------------------------------
# Planning pipeline: the plan subcommand
# ---------------------------------------------------------------------------


def run_plan(epic_number: int, resume: bool = False) -> None:
    """Run the full planning pipeline.

    Steps:
    1. Ingest epic from GitHub -> EPIC.md
    2. Assemble context -> CONTEXT.md
    3. Interactive scope discussion -> locked decisions
    4. Generate plan (Opus) -> PLAN.md + plan.json
    5a. Phase A validation (deterministic, $0)
    5b. Phase B verification (AI, ~$1-2)
    6. Human Decision Gate -> approve/revise/reject
    7. Commit + push planning artefacts

    On --resume, skips steps whose output artefacts already exist.

    Args:
        epic_number: The GitHub issue number of the epic.
        resume: If True, resume from the last completed planning step.
    """
    epic_dir = PLANNING_DIR / f"E{epic_number}"

    # Step 1: Ingest
    epic_md_path = epic_dir / "EPIC.md"
    if resume and epic_md_path.is_file():
        logger.info("Step 1 (ingest): EPIC.md exists, skipping")
    else:
        logger.info("Step 1: Ingesting epic #%d from GitHub...", epic_number)
        try:
            ingest_epic(epic_number)
        except IngestionError as exc:
            logger.error("Ingestion failed: %s", exc)
            sys.exit(1)
        logger.info("Step 1: EPIC.md written to %s", epic_md_path)

    # Step 2: Context assembly
    context_md_path = epic_dir / "CONTEXT.md"
    if resume and context_md_path.is_file():
        logger.info("Step 2 (context): CONTEXT.md exists, skipping")
    else:
        logger.info("Step 2: Assembling context...")
        try:
            assemble_context(epic_dir)
        except AssemblyError as exc:
            logger.error("Context assembly failed: %s", exc)
            sys.exit(1)
        logger.info("Step 2: CONTEXT.md written to %s", context_md_path)

    # Step 3: Interactive scope discussion
    # The orchestrator prompts the user for scope decisions interactively.
    # On --resume, if plan.json already exists, we skip scope + plan generation.
    decisions = {}
    plan_json_path = epic_dir / "plan.json"
    if resume and plan_json_path.is_file():
        logger.info("Step 3 (scope): plan.json exists, skipping scope discussion")
    else:
        decisions = _interactive_scope_discussion(epic_dir)

    # Step 4: Plan generation
    if resume and plan_json_path.is_file():
        logger.info("Step 4 (plan): plan.json exists, skipping generation")
    else:
        logger.info("Step 4: Generating plan (Opus invocation)...")
        try:
            generate_plan(epic_dir, decisions)
        except PlanGenerationError as exc:
            logger.error("Plan generation failed: %s", exc)
            sys.exit(1)
        logger.info("Step 4: PLAN.md and plan.json written")

    # Step 5: Verification (Phase A + Phase B)
    logger.info("Step 5: Verifying plan...")
    try:
        verifier_result, verified = verify_with_revision_cycle(epic_dir, decisions)
    except PlanVerificationError as exc:
        logger.error("Plan verification failed: %s", exc)
        sys.exit(1)

    if not verified:
        logger.error(
            "Plan verification failed after revision cycle. "
            "Review the verifier output and fix the plan manually."
        )
        print("\nVerifier result:")
        print(json.dumps(verifier_result, indent=2))
        sys.exit(1)

    logger.info("Step 5: Plan verified successfully")

    # Step 6: Decision Gate
    plan_md_path = epic_dir / "PLAN.md"
    gate_result = present_decision_gate(plan_md_path, verifier_result)

    if gate_result.rejected:
        logger.info("Plan rejected by human: %s", gate_result.reason)
        print("\nPlan rejected. Planning artefacts NOT committed.")
        print(f"Restart from: just epic-plan {epic_number}")
        sys.exit(0)

    if gate_result.needs_revision:
        logger.info("Human requested revision: %s", gate_result.reason)
        print("\nEdit plan.json and PLAN.md, then re-run:")
        print(f"  just epic-plan-resume {epic_number}")
        sys.exit(0)

    # Step 7: Commit + push planning artefacts
    logger.info("Step 7: Committing planning artefacts...")
    planning_files = [
        str(epic_dir / "EPIC.md"),
        str(epic_dir / "CONTEXT.md"),
        str(epic_dir / "PLAN.md"),
        str(epic_dir / "plan.json"),
    ]

    try:
        commit_hash = robust_commit(
            f"feat(workflow): plan for epic #{epic_number}",
            planning_files,
        )
        logger.info("Planning artefacts committed: %s", commit_hash)
    except GitCommitError as exc:
        logger.error("Failed to commit planning artefacts: %s", exc)
        sys.exit(1)

    try:
        git_sync()
        logger.info("Planning artefacts pushed to remote")
    except (GitConflictError, GitPushError) as exc:
        logger.warning("Failed to push planning artefacts: %s", exc)
        print(f"\nPlanning artefacts committed locally ({commit_hash}) but push failed: {exc}")
        print("Push manually: git push")

    # Post planning complete comment
    plan = _load_plan(epic_dir)
    comment_body = build_planning_complete_comment(plan)
    comment_on_epic(epic_number, comment_body)

    print(f"\nPlanning complete for epic #{epic_number}.")
    print(f"Start execution: just epic-start {epic_number}")


def _interactive_scope_discussion(epic_dir: Path) -> dict:
    """Run the interactive scope discussion with the human.

    Presents relevant architecture areas and questions from CONTEXT.md,
    then collects answers as locked scope decisions.

    In non-interactive mode (stdin is not a TTY, e.g. when run from
    `just`), skips the interactive prompt and loads existing decisions
    from decisions.json if present.

    Args:
        epic_dir: Path to the epic directory.

    Returns:
        Dict of question -> answer pairs (locked decisions).
    """
    decisions_path = epic_dir / "decisions.json"

    # Non-interactive mode: require decisions.json
    if not sys.stdin.isatty():
        if decisions_path.is_file():
            try:
                decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
                logger.info(
                    "Non-interactive mode: loaded %d decisions from %s",
                    len(decisions),
                    decisions_path,
                )
                return decisions
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse %s: %s", decisions_path, exc)
                sys.exit(1)
        logger.error(
            "Non-interactive mode requires %s. " "Create it with scope decisions before running.",
            decisions_path,
        )
        sys.exit(1)

    print("\n" + "=" * 70)
    print("SCOPE DISCUSSION")
    print("=" * 70)
    print("\nReview CONTEXT.md for detected architecture areas and questions.")
    print(f"Context file: {epic_dir / 'CONTEXT.md'}")
    print("\nEnter scope decisions as question/answer pairs.")
    print("Type 'done' when finished.\n")

    decisions: dict[str, str] = {}
    while True:
        try:
            question = input("Question (or 'done'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nScope discussion ended")
            break

        if question.lower() == "done":
            break

        if not question:
            continue

        try:
            answer = input("Answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nScope discussion ended")
            break

        if answer:
            decisions[question] = answer
            print(f"  Locked: {question} -> {answer}")

    if decisions:
        # Save decisions to a file for reference
        decisions_path.write_text(
            json.dumps(decisions, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Scope decisions saved to %s", decisions_path)

    return decisions


# ---------------------------------------------------------------------------
# Status subcommand
# ---------------------------------------------------------------------------


def show_status(epic_number: int) -> None:
    """Show the status of an epic by reading JSONL logs.

    Args:
        epic_number: The GitHub issue number of the epic.
    """
    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(f"Epic directory not found: {epic_dir}")
        sys.exit(1)

    # Check planning artefacts
    print(f"\n=== Epic #{epic_number} Status ===\n")

    artefacts = {
        "EPIC.md": epic_dir / "EPIC.md",
        "CONTEXT.md": epic_dir / "CONTEXT.md",
        "PLAN.md": epic_dir / "PLAN.md",
        "plan.json": epic_dir / "plan.json",
        "epic.jsonl": epic_dir / "epic.jsonl",
        "SUMMARY.md": epic_dir / "SUMMARY.md",
    }

    print("Planning artefacts:")
    for name, path in artefacts.items():
        exists = "EXISTS" if path.is_file() else "MISSING"
        print(f"  [{exists}] {name}")

    # Read plan.json for story info
    plan_path = epic_dir / "plan.json"
    if not plan_path.is_file():
        print(f"\nNo plan.json found. Run: just epic-plan {epic_number}")
        return

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    stories = plan.get("stories", [])

    # Read JSONL logs
    epic_log_path = epic_dir / "epic.jsonl"
    events = read_log(epic_log_path)

    # Also read story-level logs
    all_events = _collect_story_events(epic_dir, plan)

    if not events:
        print(f"\nPlan has {len(stories)} stories. Execution not started.")
        print(f"Start: just epic-start {epic_number}")
        return

    # Find run_id
    run_id = events[-1].get("run_id", "?")
    state = get_resumable_state(events, run_id)

    print(f"\nRun ID: {run_id}")
    print(f"Status: {state['next_action']}")
    print(f"Completed: {len(state['completed_stories'])}/{len(stories)}")

    if state.get("failed_story_id"):
        print(f"Failed story: {state['failed_story_id']}")

    # Show per-story status
    print("\nStories:")
    completed_set = set(state["completed_stories"])
    for i, story in enumerate(stories, 1):
        sid = story.get("story_id", "?")
        name = story.get("name", "?")
        if sid in completed_set:
            status = "DONE"
        elif sid == state.get("failed_story_id"):
            status = "FAIL"
        elif i <= len(completed_set) + 1:
            status = "NEXT"
        else:
            status = "----"
        print(f"  [{status}] {i}. {sid}: {name}")

    # Cost summary
    total_cost = sum(
        e.get("cost_usd", 0) or 0 for e in all_events if e.get("event") == "agent_complete"
    )
    if total_cost > 0:
        print(f"\nTotal cost so far: ${total_cost:.2f}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_last_attempt(events: list[dict], story_id: str) -> int:
    """Get the last attempt number for a story."""
    for e in reversed(events):
        if e.get("story_id") == story_id and "attempt" in e:
            return e["attempt"]
    return 1


def _get_last_commit(events: list[dict], story_id: str) -> str:
    """Get the commit hash from the last story_complete event for a story."""
    for e in reversed(events):
        if e.get("story_id") == story_id and e.get("event") in (
            "story_complete",
            "agent_complete",
        ):
            commit = e.get("commit")
            if commit:
                return commit
    return "unknown"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point with subcommands: plan, run, status."""
    parser = argparse.ArgumentParser(
        description="V2 Epic Orchestrator -- behavioural validation workflow",
        prog="orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # plan subcommand
    plan_parser = subparsers.add_parser(
        "plan",
        help="Run the full planning pipeline (ingest -> context -> scope -> plan -> verify -> gate)",
    )
    plan_parser.add_argument("epic_number", type=int, help="GitHub epic issue number")
    plan_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last completed planning step",
    )

    # run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Execute stories sequentially from plan.json",
    )
    run_parser.add_argument("epic_number", type=int, help="GitHub epic issue number")
    run_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last completed story",
    )

    # status subcommand
    status_parser = subparsers.add_parser(
        "status",
        help="Show epic progress from JSONL logs",
    )
    status_parser.add_argument("epic_number", type=int, help="GitHub epic issue number")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "plan":
        run_plan(args.epic_number, resume=args.resume)
    elif args.command == "run":
        run_epic(args.epic_number, resume=args.resume)
    elif args.command == "status":
        show_status(args.epic_number)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
