"""V3 epic orchestrator — outer loop + GitHub integration.

The main entry point for the V3 behavioural-validation epic workflow.
Provides two primary functions:

    run_pipeline(epic_number) — full pipeline: ingest -> repo-facts -> plan -> execute
    show_status(epic_number) — read-only JSONL inspection

The orchestrator is stateless: it reads JSONL logs, determines the
next step, builds a prompt, dispatches one agent, waits, and loops.
No AI tokens are spent on orchestration.

Reference: Epic-Workflow-Reference.md (Stages 1-4, Observability).
All imports reference workflow.*, never scripts.*.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from workflow.artifacts import (
    CritiqueRunArtifact,
    CurationCompleteArtifact,
    CurationDispatchedArtifact,
    CurationFailedArtifact,
    PhaseAValidationEventArtifact,
    PhaseBVerificationEventArtifact,
    PlannerCompleteArtifact,
    PlannerDispatchedArtifact,
    PlannerFailedArtifact,
    StoryRunArtifact,
)
from workflow.config_validator import validate_config
from workflow.dispatch import (
    EPIC_CRITIQUE_SCHEMA,
    compute_prompt_hash,
    dispatch_agent,
    estimate_tokens,
    extract_json_from_text,
    get_dispatch_params,
)
from workflow.dispatch_log import dispatch_logging, token_summary
from workflow.epic_config import (
    EpicConfig,
    ensure_epic_config,
    load_config,
)
from workflow.github_epic_comments import (
    build_critique_findings_comment,
    comment_on_epic,
)
from workflow.git_helpers import (
    GitConflictError,
    GitPushError,
    git_sync,
)
from workflow.jsonl_logger import (
    build_run_artifact,
    EventLogger,
    generate_run_id,
    get_resumable_state,
    is_story_complete,
    read_log,
)
from workflow.story_executor import execute_story

logger = logging.getLogger(__name__)
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
GH_REPO = "krazyuniks/guitar-tone-shootout"


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
        story_lines.append(f"| {i} | {story.get('name', '?')} | {model} |")

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
    story_run = StoryRunArtifact.from_events(events, story_id)

    # Find the most recent agent_complete for this story
    agent_event = None
    for e in reversed(events):
        if e.get("event") == "agent_complete" and e.get("story_id") == story_id:
            agent_event = e
            break

    turns = agent_event.get("turns", "?") if agent_event else "?"
    commit = agent_event.get("commit", "?") if agent_event else "?"

    # Count files from scope
    scope = story.get("scope", {})
    created = len(scope.get("create", []))
    modified = len(scope.get("modify", []))

    # Find validation results
    validation_section = (
        "\n".join(story_run.checkpoint_summary_lines)
        if story_run.checkpoint_summary_lines
        else "No validation checkpoint"
    )

    return f"""\
## Story Complete: {name}

**Agent:** {story_id} | **Model:** {model} | **Turns:** {turns}
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
    story_run = StoryRunArtifact.from_events(events, story_id)

    reason = story_run.failure_reason or "Unknown"
    category = story_run.failure_category or "unknown"

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

    # Commits
    commits = [
        e.get("commit", "?")
        for e in events
        if e.get("event") == "story_complete" and e.get("commit")
    ]

    return f"""\
## Epic Complete

**Stories completed:** {len(completed_ids)}/{len(stories)}
**Commits:** {", ".join(commits)}

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
# SUMMARY.md generation (deterministic, $0)
# ---------------------------------------------------------------------------


def generate_summary(epic_dir: Path, plan: dict, events: list[dict]) -> Path:
    """Generate SUMMARY.md from JSONL logs.

    A deterministic Python function ($0 AI cost) that reads the JSONL
    and renders markdown.

    Args:
        epic_dir: Path to the epic directory.
        plan: The plan.json dict.
        events: All JSONL events (epic + story level combined).

    Returns:
        Path to the generated SUMMARY.md.
    """
    stories = plan.get("stories", [])
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    story_runs = {
        story.get("story_id", ""): StoryRunArtifact.from_events(events, story.get("story_id", ""))
        for story in stories
        if story.get("story_id")
    }

    # Stories completed
    completed_ids = sorted(
        story_id for story_id, story_run in story_runs.items() if story_run.status == "complete"
    )
    # Stories failed
    failed_ids = sorted(
        story_id
        for story_id, story_run in story_runs.items()
        if story_run.status in {"failed", "exit_to_human"}
    )
    # Exit to human events
    exit_story_ids = sorted(
        story_id for story_id, story_run in story_runs.items() if story_run.status == "exit_to_human"
    )

    # Commits
    commits = [
        e.get("commit", "?")
        for e in events
        if e.get("event") == "story_complete" and e.get("commit")
    ]

    # Validation checkpoint results
    validation_results = []
    for story_id in sorted(story_runs):
        checkpoint = story_runs[story_id].last_checkpoint
        if checkpoint is None:
            continue

        status = "PASS" if checkpoint.passed else "FAIL"
        criteria_count = len(checkpoint.results)
        validation_results.append(
            f"| {story_id} | {checkpoint.check_type} | {status} | {criteria_count} |"
        )

    # Failure details
    failure_lines = []
    for sid in failed_ids:
        story_run = story_runs[sid]
        category = story_run.failure_category or "unknown"
        reason = story_run.failure_reason or "Unknown"
        failure_lines.append(f"- **{sid}** [{category}]: {reason}")

    # Deferred/unresolved items
    deferred_lines = []
    for story_id in exit_story_ids:
        story_run = story_runs[story_id]
        category = story_run.failure_category or "unknown"
        reason = story_run.failure_reason or "Unknown"
        deferred_lines.append(f"- **{story_id}** [{category}]: {reason}")

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


def _derive_key_entities(file_paths: list[str]) -> list[str]:
    """Derive human-readable entity names from created file paths.

    Applies naming conventions:
    - libs/*/domain/*.py       -> stem + "Model"
    - webapp/api/v1/*.py       -> "/api/v1/" + stem (URL path)
    - */repositories/*.py      -> stem + "Repository"
    - webapp/services/*.py     -> stem + "Service"
    - infrastructure/migrations/versions/*.py -> skip
    - Other .py files          -> stem as-is

    Returns a deduplicated list preserving order.
    """
    seen: set[str] = set()
    entities: list[str] = []

    for path in file_paths:
        p = Path(path)

        # Skip migration files
        if "migrations" in p.parts and "versions" in p.parts:
            continue

        stem = p.stem
        if not stem:
            continue

        parts = p.parts

        # Domain models: libs/<bc>/domain/<name>.py
        if len(parts) >= 3 and "domain" in parts:
            entity = stem.capitalize() + "Model"
        # API routes: webapp/api/v1/<name>.py
        elif len(parts) >= 3 and "api" in parts:
            # Reconstruct URL path from the api/ segment onwards
            try:
                api_idx = parts.index("api")
                url_parts = parts[api_idx:-1]  # exclude filename
                entity = "/" + "/".join(url_parts) + "/" + stem
            except ValueError:
                entity = stem
        # Repositories: any path containing "repositories" or "repository"
        elif any(part in ("repositories", "repository") for part in parts):
            entity = stem.capitalize() + "Repository"
        # Services: webapp/services/<name>.py
        elif "services" in parts:
            entity = stem.capitalize() + "Service"
        else:
            entity = stem

        if entity and entity not in seen:
            seen.add(entity)
            entities.append(entity)

    return entities


# ---------------------------------------------------------------------------
# STORY_CONTEXT.md generation (deterministic, $0)
# ---------------------------------------------------------------------------


def generate_story_context(
    epic_dir: Path,
    plan: dict,
    events: list[dict],
    run_id: str,
) -> Path:
    """Generate STORY_CONTEXT.md from JSONL logs, plan.json, and git state.

    A deterministic Python function ($0 AI cost) that provides epic-level
    context for story agents. Regenerated after each story_complete event
    so the next agent sees current state.

    Contents:
    - Epic number, goal, and GitHub issue link (from plan.json + epic_dir name)
    - Story progress: per-story commit, changes summary, key files, state changes
    - Current DB migration head
    - Queue topology (from app consumer files)
    - Deleted files (from git diff of completed story commits)
    - Deferred critique findings as advisory notes
    - Pending stories with names

    Args:
        epic_dir: Path to the epic directory.
        plan: The plan.json dict.
        events: All JSONL events (epic + story level combined).
        run_id: Current run ID (to scope completed stories).

    Returns:
        Path to the generated STORY_CONTEXT.md.
    """
    stories = plan.get("stories", [])
    goal = plan.get("goal", "(no goal)")

    # Epic number from directory name (e.g. "E120" → "120")
    raw = epic_dir.name.lstrip("E")
    epic_num = raw if raw.isdigit() else epic_dir.name
    issue_url = f"https://github.com/krazyuniks/guitar-tone-shootout/issues/{epic_num}"

    # Completed story IDs (scoped to this run)
    completed_ids = sorted(
        {
            e["story_id"]
            for e in events
            if e.get("event") == "story_complete" and e.get("run_id") == run_id
        }
    )
    completed_set = set(completed_ids)

    # Current DB migration head
    migration_head = _get_migration_head()

    # Queue topology
    queue_lines = _get_queue_topology()
    critique_runs: list[CritiqueRunArtifact] = []
    for event in events:
        if event.get("run_id") != run_id:
            continue
        try:
            critique_run = CritiqueRunArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            continue
        if critique_run.level == "story" and critique_run.failed and critique_run.normalized_findings:
            critique_runs.append(critique_run)

    # --- Header ---
    lines: list[str] = [
        "# Story Context",
        "",
        f"**Epic:** #{epic_num} — [GitHub Issue]({issue_url})",
        f"**Goal:** {goal}",
        f"**Progress:** {len(completed_ids)}/{len(stories)} stories complete",
        f"**Migration head:** {migration_head}",
    ]

    if queue_lines:
        lines += ["", "## Queue Topology", "", *queue_lines]

    # --- Observable Truths ---
    observable_truths = plan.get("observable_truths", [])
    if observable_truths:
        lines += ["", "## Observable Truths", ""]
        for truth in observable_truths:
            truth_id = truth.get("id", "?")
            statement = truth.get("statement", "?")
            lines.append(f"{truth_id}. {statement}")

    # --- Key Decisions ---
    # Collect implementation notes from completed stories
    key_decision_lines: list[str] = []
    for story in stories:
        sid = story.get("story_id", "?")
        if sid in completed_set:
            for note in story.get("implementation_notes", []):
                key_decision_lines.append(f"- [{sid}] {note}")

    for critique_run in critique_runs:
        for finding in critique_run.normalized_findings:
            key_decision_lines.append(f"- [critique] {finding.issue or finding.summary_text}")

    if key_decision_lines:
        lines += ["", "## Key Decisions", "", *key_decision_lines]

    # --- Stories ---
    lines += ["", "## Stories", ""]

    for story in stories:
        sid = story.get("story_id", "?")
        name = story.get("name", "?")

        if sid in completed_set:
            # Get commit hash for this story
            commit = "?"
            for e in reversed(events):
                if (
                    e.get("story_id") == sid
                    and e.get("event") == "story_complete"
                    and e.get("run_id") == run_id
                ):
                    commit = e.get("commit", "?")
                    break

            diff_summary = _git_diff_stat(commit)

            # Key files from story scope
            scope = story.get("scope", {})
            created_files = scope.get("create", [])
            key_files = created_files + scope.get("modify", [])

            # State changes: table renames from migration files in this commit
            migration_renames = _extract_migration_renames(commit)

            # Files deleted in this commit
            deleted_files = _get_deleted_files(commit)

            lines.append(f"### ✅ {sid}: {name} (`{commit[:8]}`)")
            lines.append("")
            lines.append(f"- **Changes:** {diff_summary}")

            # Created files (up to 6)
            if created_files:
                created_str = ", ".join(f"`{f}`" for f in created_files[:6])
                lines.append(f"- **Created:** {created_str}")

            # Key entities derived from created file paths
            key_entities = _derive_key_entities(created_files)
            if key_entities:
                lines.append(f"- **Key entities:** {', '.join(key_entities)}")

            if key_files:
                files_str = ", ".join(f"`{f}`" for f in key_files[:6])
                if len(key_files) > 6:
                    files_str += f" +{len(key_files) - 6} more"
                lines.append(f"- **Key files:** {files_str}")

            if migration_renames:
                pairs = ", ".join(f"{old}→{new}" for old, new in migration_renames[:12])
                if len(migration_renames) > 12:
                    pairs += " ..."
                lines.append(f"- **Table renames ({len(migration_renames)}):** {pairs}")

            if deleted_files:
                del_str = ", ".join(f"`{f}`" for f in deleted_files[:5])
                if len(deleted_files) > 5:
                    del_str += f" +{len(deleted_files) - 5} more"
                lines.append(f"- **Deleted:** {del_str}")

        else:
            lines.append(f"### ⏳ {sid}: {name}")
            lines.append("")
            lines.append("- (pending)")

        lines.append("")

    # --- Advisory Notes ---
    advisory_lines: list[str] = []
    for critique_run in critique_runs:
        story_label = critique_run.story_id or "?"
        for finding in critique_run.normalized_findings:
            severity = finding.severity or "?"
            issue = finding.issue or finding.summary_text
            advisory_lines.append(f"- [{severity}] {story_label}: {issue}")

    if advisory_lines:
        lines += ["## Advisory Notes", "", *advisory_lines, ""]

    content = "\n".join(lines) + "\n"
    context_path = epic_dir / "STORY_CONTEXT.md"
    context_path.write_text(content, encoding="utf-8")

    logger.info("STORY_CONTEXT.md generated at %s", context_path)
    return context_path


def _git_diff_stat(commit: str) -> str:
    """Get a one-line diff stat summary for a commit.

    Returns something like "5 files changed, 120 insertions(+), 30 deletions(-)".
    Falls back to a placeholder if git is unavailable or the commit is unknown.
    """
    if not commit or commit in ("?", "unknown"):
        return "no commit info"
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", f"{commit}~1..{commit}"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Last line of --stat is the summary
            stat_lines = result.stdout.strip().splitlines()
            return stat_lines[-1].strip() if stat_lines else "no changes"
        return "diff unavailable"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "diff unavailable"


def _get_migration_head() -> str:
    """Get the latest Alembic migration revision from the migrations directory.

    Reads migration filenames to find the highest-numbered revision.
    This is a filesystem check, not a database check.
    """
    migrations_dir = PROJECT_ROOT / "infrastructure" / "migrations" / "versions"
    if not migrations_dir.is_dir():
        return "unknown"

    # Find all migration files matching NNNN_*.py pattern
    revisions: list[str] = []
    for f in migrations_dir.iterdir():
        if f.suffix == ".py" and f.name[0].isdigit():
            revisions.append(f.stem)

    if not revisions:
        return "none"

    # Sort and return the latest
    revisions.sort()
    return revisions[-1]


def _extract_migration_renames(commit: str) -> list[tuple[str, str]]:
    """Extract table rename pairs from migration files added in a commit.

    Looks for ("old", "new") tuples in migration files that were added as
    part of the given commit. Used to surface table renames in STORY_CONTEXT.md
    so agents know about schema changes from prior stories.

    Returns a list of (old_name, new_name) tuples.
    """
    if not commit or commit in ("?", "unknown"):
        return []
    try:
        result = subprocess.run(
            ["git", "show", "--name-status", "--diff-filter=A", commit],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        migration_files: list[Path] = []
        for line in result.stdout.splitlines():
            if line.startswith("A\t") and "migrations/versions" in line and line.endswith(".py"):
                migration_files.append(PROJECT_ROOT / line[2:].strip())

        renames: list[tuple[str, str]] = []
        pair_re = re.compile(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)')
        for mf in migration_files:
            if mf.is_file():
                renames.extend(pair_re.findall(mf.read_text(encoding="utf-8")))

        return renames
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _get_deleted_files(commit: str) -> list[str]:
    """Get list of files deleted in a commit.

    Returns relative file paths for files with status D in the given commit.
    """
    if not commit or commit in ("?", "unknown"):
        return []
    try:
        result = subprocess.run(
            ["git", "show", "--name-status", "--diff-filter=D", commit],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [line[2:].strip() for line in result.stdout.splitlines() if line.startswith("D\t")]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_queue_topology() -> list[str]:
    """Extract queue names from app consumer files.

    Searches apps/*/src/*/consumer.py for queue_name= assignments.
    Returns formatted lines for the STORY_CONTEXT queue topology section.
    """
    apps_dir = PROJECT_ROOT / "apps"
    if not apps_dir.is_dir():
        return []

    queue_re = re.compile(r'queue_name\s*=\s*["\']([^"\']+)["\']')
    lines: list[str] = []
    for consumer in sorted(apps_dir.glob("*/src/*/consumer.py")):
        try:
            text = consumer.read_text(encoding="utf-8")
            matches = queue_re.findall(text)
            if matches:
                app_name = consumer.relative_to(PROJECT_ROOT).parts[1]
                for q in matches:
                    lines.append(f"- `{q}` — consumed by `{app_name}`")
        except OSError:
            continue
    return lines


# ---------------------------------------------------------------------------
# Post-epic Opus critique
# ---------------------------------------------------------------------------


def _run_epic_critique(
    plan: dict,
    epic_dir: Path,
    events: list[dict],
    epic_logger: EventLogger,
    config: EpicConfig | None = None,
) -> CritiqueRunArtifact:
    """Run post-epic critique on the full implementation.

    Dispatches a read-only agent with the critique_epic template
    to review the entire epic holistically.

    Args:
        plan: The plan.json dict.
        epic_dir: Path to the epic directory.
        events: All JSONL events (epic + story combined).
        epic_logger: Epic-level JSONL event logger.
        config: Epic configuration profile. If None, falls back to defaults.

    Returns:
        Typed critique result for the full epic.
    """
    # Read template
    template_path = Path(__file__).resolve().parent / "templates" / "critique_epic.md"
    template = template_path.read_text(encoding="utf-8")

    # Read EPIC.md
    epic_md_path = epic_dir / "EPIC.md"
    epic_md = epic_md_path.read_text(encoding="utf-8") if epic_md_path.exists() else "(unavailable)"

    # Get first story commit from JSONL events
    first_commit = None
    for e in events:
        if e.get("event") == "story_complete" and e.get("commit"):
            first_commit = e["commit"]
            break

    # Get full git diff from first story commit to HEAD
    if first_commit and first_commit != "unknown":
        try:
            diff_result = subprocess.run(
                ["git", "diff", f"{first_commit}~1..HEAD"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=30,
            )
            git_diff = diff_result.stdout or "(no diff)"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            git_diff = "(diff unavailable)"
    else:
        git_diff = "(no commit reference available)"

    # Build event summary from JSONL
    summary_events = []
    for e in events:
        event_type = e.get("event", "")
        if event_type in (
            "story_complete",
            "story_failed",
            "validation_pass",
            "validation_fail",
            "agent_complete",
            "critique_pass",
            "critique_fail",
        ):
            summary_events.append(
                {
                    "event": event_type,
                    "story_id": e.get("story_id", ""),
                    "attempt": e.get("attempt"),
                }
            )
    event_summary = json.dumps(summary_events, indent=2)

    # Build prompt from template
    plan_json = json.dumps(plan, indent=2)
    prompt = template.replace("{{ epic_md }}", epic_md)
    prompt = prompt.replace("{{ plan_json }}", plan_json)
    prompt = prompt.replace("{{ git_diff }}", git_diff)
    prompt = prompt.replace("{{ event_summary }}", event_summary)

    # Resolve model from config
    critique_model = config.models.epic_critic if config else "opus"

    # Log critique dispatch
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)
    epic_logger.log_event(
        "epic_critique_dispatched",
        critique_type="epic",
        critique_model=critique_model,
        adapter="codex" if critique_model == "codex" else "claude",
        role="critique_epic",
        prompt_hash=prompt_hash,
        prompt_tokens=prompt_tokens,
    )

    # Dispatch read-only critique agent with schema enforcement
    mcp_servers, timeout = get_dispatch_params("critique", config)
    result = dispatch_agent(
        prompt=prompt,
        model=critique_model,
        json_schema=EPIC_CRITIQUE_SCHEMA,
        mcp_servers=mcp_servers,
        timeout=timeout,
        cwd=PROJECT_ROOT,
        role="epic_critique",
    )

    if not result.success:
        logger.warning(
            "Epic critique dispatch failed (exit_code=%d)",
            result.exit_code,
        )
        critique_run = CritiqueRunArtifact.for_error(
            level="epic",
            critique_type="epic",
            critique_model=critique_model,
            error=result.output[:500] if result.output else "Dispatch failed",
            raw_response=result.output or "",
        )
        epic_logger.log_event(critique_run.event_name, **critique_run.event_payload)
        # Dispatch failure is fail-closed (invariant E2)
        return CritiqueRunArtifact.for_error(
            level="epic",
            critique_type="epic",
            critique_model=critique_model,
            error="Epic critique dispatch failed",
            raw_response=result.output or "",
        )

    # Parse JSON result — robust extraction handles text around JSON
    try:
        critique = extract_json_from_text(result.output or "")
    except ValueError:
        output_preview = (result.output or "")[:200]
        logger.warning("Epic critique returned invalid JSON")
        critique_run = CritiqueRunArtifact.for_error(
            level="epic",
            critique_type="epic",
            critique_model=critique_model,
            error=f"Invalid JSON: {output_preview}",
            raw_response=result.output or "",
        )
        epic_logger.log_event(critique_run.event_name, **critique_run.event_payload)
        # Parse failure is fail-closed (invariant E2)
        return CritiqueRunArtifact.for_error(
            level="epic",
            critique_type="epic",
            critique_model=critique_model,
            error="Epic critique returned invalid JSON",
            raw_response=result.output or "",
        )

    critique_run = CritiqueRunArtifact.from_dict(
        critique,
        level="epic",
        critique_type="epic",
        critique_model=critique_model,
        turns=result.turns,
        raw_response=result.output or "",
    )
    epic_logger.log_event(critique_run.event_name, **critique_run.event_payload)
    return critique_run


# ---------------------------------------------------------------------------
# Plan and event loading helpers
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
    return build_run_artifact(events, run_id).next_action == "exit_to_human"


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
# Epic execution: the outer loop (Stage 4)
# ---------------------------------------------------------------------------


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

    # Load epic configuration profile
    config_path = ensure_epic_config(epic_dir)
    try:
        config = load_config(override_path=config_path)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # Pre-execution validation (skip golden path by default — it's slow)
    logger.info("Running pre-execution configuration validation...")
    validation = validate_config(PROJECT_ROOT, skip_golden_path=True)
    if not validation.passed:
        logger.warning("Pre-execution validation failed:\n%s", validation.summary())
        if sys.stdin.isatty():
            if not typer.confirm("Continue despite preflight failures?", default=False):
                sys.exit(1)
        else:
            logger.warning("Non-interactive mode — continuing despite preflight failures")
    else:
        logger.info("Pre-execution validation passed.")

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

    # Sync agent configuration before execution
    try:
        subprocess.run(
            ["agent-sync", "--quiet"],
            cwd=PROJECT_ROOT,
            timeout=30,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("agent-sync not available or timed out, continuing")

    # Activate unified dispatch logging for all dispatch_agent() calls
    with dispatch_logging(epic_dir, run_id):
        _run_epic_loop(
            epic_number=epic_number,
            epic_dir=epic_dir,
            epic_log_path=epic_log_path,
            epic_logger=epic_logger,
            plan=plan,
            run_id=run_id,
            config=config,
            completed_stories=completed_stories,
        )

    # Print token usage summary
    summary = token_summary(epic_dir, run_id)
    console.print(f"\n[bold]Dispatch Token Summary[/bold]\n{summary}")


def _run_epic_loop(
    *,
    epic_number: int,
    epic_dir: Path,
    epic_log_path: Path,
    epic_logger: EventLogger,
    plan: dict,
    run_id: str,
    config: EpicConfig,
    completed_stories: list[str],
) -> None:
    """Inner execution loop for an epic run (extracted for dispatch_logging scope)."""
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
            # All stories complete -- run epic critique before finishing
            logger.info("All stories complete for epic #%d. Running epic critique...", epic_number)

            all_events = _collect_story_events(epic_dir, plan)

            critique_run = _run_epic_critique(
                plan=plan,
                epic_dir=epic_dir,
                events=all_events,
                epic_logger=epic_logger,
                config=config,
            )

            if not critique_run.passed:
                logger.warning(
                    "Epic critique found %d advisory finding(s). Continuing pipeline.",
                    critique_run.findings_count,
                )
                critique_body = build_critique_findings_comment(
                    gate_type="epic",
                    critique_run=critique_run,
                )
                url = comment_on_epic(epic_number, critique_body)
                if url:
                    epic_logger.log_event(
                        "github_comment",
                        epic=epic_number,
                        comment_url=url,
                    )

            # Critique is advisory; continue to epic completion either way.
            epic_logger.log_event(
                "epic_complete",
                epic=epic_number,
                stories_completed=len(completed_stories),
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
            config=config,
            epic_number=epic_number,
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

            # Regenerate STORY_CONTEXT.md so the next agent sees current state
            all_events = _collect_story_events(epic_dir, plan)
            generate_story_context(epic_dir, plan, all_events, run_id)

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
            except GitConflictError as exc:
                logger.error(
                    "Git conflict after story '%s': %s. Exiting to human review.",
                    story_id,
                    exc,
                )
                epic_logger.log_event(
                    "exit_to_human",
                    story_id=story_id,
                    reason=f"Git merge conflict: {exc}",
                    failure_category="env",
                    context={"conflicting_files": exc.conflicting_files},
                )
                break
            except GitPushError as exc:
                logger.warning("Git push failed after story '%s': %s", story_id, exc)
        else:
            # Story failed — post failure comment and exit
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
# Full pipeline: run_pipeline (unified entry point for `just epic N`)
# ---------------------------------------------------------------------------


def run_pipeline(epic_number: int) -> None:
    """Idempotent epic pipeline entry point.

    Reads JSONL state and does the next thing. The happy path is one run:

    1. ``just epic N`` — plan, verify, approve, commit, and continue into execution
    2. rerun ``just epic N`` only if recovery/resume is needed after interruption

    Args:
        epic_number: The GitHub issue number of the epic.
    """
    from workflow.cli import PlanningPipelineOutcome, _check_plan_committed, _run_planning_pipeline

    epic_dir = PLANNING_DIR / f"E{epic_number}"

    # Gate 1: plan_committed
    if not _check_plan_committed(epic_dir):
        planning_outcome = _run_planning_pipeline(epic_number)
        if planning_outcome != PlanningPipelineOutcome.COMMITTED:
            return
        logger.info("Planning committed for epic #%d. Continuing into execution.", epic_number)
    else:
        logger.info("Plan already committed for epic #%d.", epic_number)

    # Stage 4: Execution (test generation happens per-story, after implementation)
    logger.info("Starting story execution for epic #%d.", epic_number)
    run_epic(epic_number, resume=True)


# ---------------------------------------------------------------------------
# Status: show_status (read-only JSONL inspection)
# ---------------------------------------------------------------------------


def show_status(epic_number: int) -> None:
    """Show the status of an epic by reading JSONL logs.

    Reads epic.jsonl and per-story logs to present:
    - Pipeline stage (planning, execution, complete, failed)
    - Planning status (planner attempts, Phase A/B results, gate outcome)
    - Per-story table (ID, status, attempt count, cost)
    - Totals (completed/failed/remaining, total cost)
    - Failures (most recent failure category and context)

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
        "repo_facts.json": epic_dir / "repo_facts.json",
        "CURATION.md": epic_dir / "CURATION.md",
        "curation.json": epic_dir / "curation.json",
        "PLAN.md": epic_dir / "PLAN.md",
        "plan.json": epic_dir / "plan.json",
        "epic.jsonl": epic_dir / "epic.jsonl",
        "SUMMARY.md": epic_dir / "SUMMARY.md",
    }

    print("Planning artefacts:")
    for name, path in artefacts.items():
        exists = "EXISTS" if path.is_file() else "MISSING"
        print(f"  [{exists}] {name}")

    # Determine pipeline stage
    has_plan = (epic_dir / "plan.json").is_file()
    has_epic_log = (epic_dir / "epic.jsonl").is_file()

    if not has_plan:
        print("\nPipeline stage: PLANNING (no plan.json)")
        print(f"Run: just epic {epic_number}")
        return

    plan = json.loads((epic_dir / "plan.json").read_text(encoding="utf-8"))
    stories = plan.get("stories", [])

    if not has_epic_log:
        print("\nPipeline stage: PLANNED (plan exists, no execution log)")
        print(f"Plan has {len(stories)} stories.")
        print(f"Run: just epic {epic_number}")
        return

    # Read JSONL logs
    epic_log_path = epic_dir / "epic.jsonl"
    events = read_log(epic_log_path)
    all_events = _collect_story_events(epic_dir, plan)

    if not events:
        print("\nPipeline stage: PLANNED (empty log)")
        print(f"Plan has {len(stories)} stories. Execution not started.")
        return

    # Find run_id
    run_id = events[-1].get("run_id", "?")
    run_artifact = build_run_artifact(
        events,
        run_id,
        epic_number=epic_number,
        has_plan=True,
    )
    state = run_artifact.to_resume_state()
    stage = run_artifact.stage.upper()

    print(f"\nPipeline stage: {stage}")
    print(f"Run ID: {run_id}")
    print(f"Status: {run_artifact.next_action}")
    print(f"Completed: {len(run_artifact.completed_stories)}/{len(stories)}")

    # Show gate status
    print("\nGates:")
    print(f"  plan_committed:  {'YES' if run_artifact.stage in ('execution', 'complete', 'failed') else 'no'}")

    if run_artifact.failed_story_id:
        print(f"Failed story: {run_artifact.failed_story_id}")

    # Planning status
    curation_dispatches: list[CurationDispatchedArtifact] = []
    curation_result: CurationCompleteArtifact | CurationFailedArtifact | None = None
    planner_dispatches: list[PlannerDispatchedArtifact] = []
    planner_result: PlannerCompleteArtifact | PlannerFailedArtifact | None = None
    phase_a_event: PhaseAValidationEventArtifact | None = None
    phase_b_event: PhaseBVerificationEventArtifact | None = None

    for event in events:
        try:
            curation_dispatches.append(CurationDispatchedArtifact.from_event(event))
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            curation_result = CurationCompleteArtifact.from_event(event)
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            curation_result = CurationFailedArtifact.from_event(event)
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            planner_dispatches.append(PlannerDispatchedArtifact.from_event(event))
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            planner_result = PlannerCompleteArtifact.from_event(event)
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            planner_result = PlannerFailedArtifact.from_event(event)
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            phase_a_event = PhaseAValidationEventArtifact.from_event(event)
            continue
        except (KeyError, TypeError, ValueError):
            pass

        try:
            phase_b_event = PhaseBVerificationEventArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            pass
    gate_events = [
        e for e in events if e.get("event") in ("plan_approved", "plan_revised", "plan_rejected")
    ]

    if (
        curation_dispatches
        or curation_result is not None
        or planner_dispatches
        or planner_result is not None
        or phase_a_event is not None
        or phase_b_event is not None
        or gate_events
    ):
        print("\nPlanning:")
        if curation_dispatches:
            print(f"  Curation attempts: {len(curation_dispatches)}")
        if curation_result is not None:
            curation_status = (
                "COMPLETE" if isinstance(curation_result, CurationCompleteArtifact) else "FAILED"
            )
            print(f"  Curation: {curation_status}")
        if planner_dispatches:
            print(f"  Planner attempts: {len(planner_dispatches)}")
        if planner_result is not None:
            planner_status = "COMPLETE" if isinstance(planner_result, PlannerCompleteArtifact) else "FAILED"
            print(f"  Planner: {planner_status}")
        if phase_a_event is not None:
            print(f"  Phase A: {'PASS' if phase_a_event.passed else 'FAIL'}")
        if phase_b_event is not None:
            print(f"  Phase B: {'PASS' if phase_b_event.passed else 'FAIL'}")
        if run_artifact.decision_gate:
            print(f"  Decision gate: {run_artifact.decision_gate.upper()}")

    # Show per-story status
    print("\nStories:")
    completed_set = set(run_artifact.completed_stories)
    for i, story in enumerate(stories, 1):
        sid = story.get("story_id", "?")
        name = story.get("name", "?")

        if sid in completed_set:
            status = "DONE"
        elif sid == run_artifact.failed_story_id:
            status = "FAIL"
        elif i <= len(completed_set) + 1:
            status = "NEXT"
        else:
            status = "----"
        print(f"  [{status}] {i}. {sid}: {name}")

    # Recent failures
    failure_story_ids = [
        e.get("story_id")
        for e in all_events
        if e.get("event") in ("story_failed", "exit_to_human")
        and e.get("run_id") == run_id
        and e.get("story_id")
    ]
    seen_failure_story_ids: set[str] = set()
    recent_failures: list[tuple[str, StoryRunArtifact]] = []
    for story_id in reversed(failure_story_ids):
        if story_id in seen_failure_story_ids:
            continue
        seen_failure_story_ids.add(story_id)
        recent_failures.append((story_id, StoryRunArtifact.from_events(all_events, story_id)))
        if len(recent_failures) == 3:
            break
    if recent_failures:
        print("\nRecent failures:")
        for sid, story_run in reversed(recent_failures):
            reason = story_run.failure_reason or "Unknown"
            category = story_run.failure_category or "unknown"
            print(f"  {sid}: [{category}] {reason[:120]}")

    # Dispatch token summary
    dispatch_summary = token_summary(epic_dir, run_id)
    if not dispatch_summary.startswith("No dispatch"):
        print(f"\nToken Usage:\n{dispatch_summary}")
