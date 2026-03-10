"""JSONL event logging system for the V2 epic workflow.

Provides crash-safe, append-only event logging with structured JSONL.
Supports crash recovery, idempotency checks, and run resumption.
No dependency on run_epic.py or any V1 code.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from workflow.artifacts import RunArtifact, RunEventArtifact

SCHEMA_VERSION = 2


class EventLogger:
    """Append-only JSONL event logger with flush-per-line for crash safety.

    Each logged event is written as a single JSON line and immediately
    flushed to disk. This ensures that even if the process crashes
    mid-execution, all previously logged events are recoverable.

    Args:
        log_path: Path to the JSONL log file (created if it does not exist).
        run_id: UUID string identifying this execution run.
    """

    def __init__(self, log_path: Path, run_id: str) -> None:
        self.log_path = log_path
        self.run_id = run_id
        self._last_ts: datetime | None = None

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: str, **kwargs: object) -> None:
        """Append a single JSONL event line with universal fields.

        Universal fields (schema_v, run_id, ts, event) are added
        automatically. Additional event-specific fields are passed as
        keyword arguments.

        The timestamp is guaranteed to be monotonically increasing
        within a run — if two events occur within the same microsecond,
        the second is bumped forward by one microsecond.

        Args:
            event: Event type string (e.g. "story_started", "epic_complete").
            **kwargs: Event-specific fields merged into the log entry.
        """
        now = datetime.now(UTC)

        # Enforce monotonically increasing timestamps
        if self._last_ts is not None and now <= self._last_ts:
            now = self._last_ts.replace(microsecond=self._last_ts.microsecond + 1)
        self._last_ts = now

        entry = RunEventArtifact(
            schema_v=SCHEMA_VERSION,
            run_id=self.run_id,
            ts=now.isoformat(),
            event=event,
            data=dict(kwargs),
        )

        line = json.dumps(entry.to_dict(), default=str)

        with self.log_path.open("a") as f:
            f.write(line + "\n")
            f.flush()


def read_log(log_path: Path) -> list[dict]:
    """Read all events from a JSONL log file.

    Handles partial last lines gracefully — if the process crashed
    mid-write, the incomplete trailing line is silently discarded.
    Empty files return an empty list.

    Args:
        log_path: Path to the JSONL log file.

    Returns:
        List of parsed event dictionaries, in chronological order.
    """
    if not log_path.exists():
        return []

    return [event.to_dict() for event in read_event_log(log_path)]


def read_event_log(log_path: Path) -> list[RunEventArtifact]:
    """Read typed event artifacts from a JSONL log file."""
    if not log_path.exists():
        return []

    events: list[RunEventArtifact] = []
    raw = log_path.read_text()

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(RunEventArtifact.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Partial last line from a crash — discard it silently.
            # Only the final line can be partial (append-only + flush-per-line),
            # so we continue parsing in case there are blank lines interspersed.
            continue

    return events


def find_last_event(
    events: list[dict],
    event_type: str,
    **filters: object,
) -> dict | None:
    """Find the most recent event matching type and optional field filters.

    Searches events in reverse chronological order (last to first).

    Args:
        events: List of event dicts (from read_log).
        event_type: The event type to match (e.g. "story_complete").
        **filters: Additional field=value pairs that must all match.
            For example: story_id="01-architecture", attempt=1.

    Returns:
        The matching event dict, or None if no match is found.
    """
    for event in reversed(events):
        if event.get("event") != event_type:
            continue
        if all(event.get(k) == v for k, v in filters.items()):
            return event
    return None


def is_story_complete(
    events: list[dict],
    story_id: str,
    run_id: str,
) -> bool:
    """Check if a story_complete event exists for a given story and run.

    This is the idempotency check — if a story has already been completed
    in this run, it should not be re-executed on resume.

    Args:
        events: List of event dicts (from read_log).
        story_id: The story identifier to check.
        run_id: The run ID to scope the check to.

    Returns:
        True if the story is complete in this run, False otherwise.
    """
    return (
        find_last_event(
            events,
            "story_complete",
            story_id=story_id,
            run_id=run_id,
        )
        is not None
    )


def generate_run_id() -> str:
    """Generate a new UUID4 string for a fresh orchestrator run.

    A new run_id is generated ONLY when explicitly starting a new run,
    not when resuming an existing one. On resume, the orchestrator
    reuses the run_id from the latest run in the JSONL log.

    Returns:
        UUID4 string (e.g. "a1b2c3d4-e5f6-7890-abcd-ef1234567890").
    """
    return str(uuid.uuid4())


def get_resumable_state(
    events: list[dict],
    run_id: str,
) -> dict:
    """Determine the resumption point from a JSONL log for a given run.

    Analyses the event history to find:
    - Which stories have been completed in this run
    - What the last significant event was
    - What the next action should be
    - Whether test generation is complete

    This is used for crash recovery: the orchestrator reads the log,
    finds the latest run_id, and calls this function to determine
    where to resume.

    Args:
        events: List of event dicts (from read_log).
        run_id: The run ID to analyse.

    Returns:
        A dict with:
        - completed_stories: list of story_id strings that are done
        - last_event: the most recent event dict for this run (or None)
        - next_action: one of "continue", "retry_story", "exit_to_human",
          "epic_complete", "test_generation", or "start"
        - failed_story_id: story_id of the last failed story (if applicable)
        - stories_with_passing_tests: list of story_id strings with passing tests
    """
    return build_run_artifact(events, run_id).to_resume_state()


def build_run_artifact(
    events: list[dict],
    run_id: str,
    *,
    epic_number: int | None = None,
    has_plan: bool = False,
) -> RunArtifact:
    """Build a typed run snapshot from JSONL event dictionaries."""
    return RunArtifact.from_logs(
        events,
        run_id,
        epic_number=epic_number,
        has_plan=has_plan,
    )


def is_test_generation_complete(
    events: list[dict],
    stories_with_specs: list[str],
) -> bool:
    """Check if test generation is complete for all stories that need tests.

    Compares stories that have test_specs against stories with
    test_review_pass events. Test generation is complete when every
    story with a test_spec has a passing test.

    Not scoped to run_id — test_review_pass events are valid across
    runs (matching _is_test_already_passing in test_generator.py).

    Args:
        events: List of event dicts (from read_log).
        stories_with_specs: List of story_id strings that have test_specs.

    Returns:
        True if all stories with specs have passing tests, or if
        there are no stories with specs.
    """
    if not stories_with_specs:
        return True

    passed_stories = {
        e["story_id"]
        for e in events
        if e.get("event") == "test_review_pass" and "story_id" in e
    }

    return all(sid in passed_stories for sid in stories_with_specs)
