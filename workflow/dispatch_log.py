"""Unified dispatch logging with prompt/response pairing and token tracking.

Centralises all dispatch logging into a single JSONL file per epic run
with content-addressed prompt/response storage. Replaces the scattered
ad-hoc file writing (_log_dispatch_prompt, codex-response-*, last-planner-output).

Each dispatch_agent() call is automatically recorded when a DispatchLog
is active via the dispatch_logging() context manager. A dispatch writes a
`started` entry when it is launched and a `completed` entry when it exits.

Reference: GitHub issue #153.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime

from workflow.artifacts import DispatchArtifact
from workflow.dispatch import compute_prompt_hash, estimate_tokens

logger = logging.getLogger(__name__)

# Module-level active dispatch log — set by dispatch_logging() context manager.
# dispatch_agent() checks this and records entries automatically.
_active_dispatch_log: DispatchLog | None = None


def get_active_dispatch_log() -> DispatchLog | None:
    """Return the currently active dispatch log, or None."""
    return _active_dispatch_log


@dataclass(frozen=True)
class DispatchRecord:
    """Paths and ids for one logged dispatch lifecycle."""

    dispatch_id: str
    prompt_hash: str
    prompt_file: str
    response_file: str
    conversation_file: str
    conversation_path: Path


class DispatchLog:
    """Unified dispatch log for an epic run.

    Writes one JSONL entry per dispatch_agent() call to ``dispatch.jsonl``
    in the epic directory. Prompts and responses are stored in a
    ``dispatches/`` subdirectory, keyed by prompt hash for deduplication.

    Args:
        epic_dir: Path to the epic directory (e.g. ``.planning/epics/E95``).
        run_id: UUID string identifying this execution run.
    """

    def __init__(self, epic_dir: Path, run_id: str) -> None:
        self.epic_dir = epic_dir
        self.run_id = run_id
        self.log_path = epic_dir / "dispatch.jsonl"
        self.dispatches_dir = epic_dir / "dispatches"
        self.dispatches_dir.mkdir(parents=True, exist_ok=True)

    def _append_entry(self, entry: dict) -> None:
        """Append one JSONL entry to dispatch.jsonl."""
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
                f.flush()
        except OSError as exc:
            logger.warning("Failed to write dispatch log entry: %s", exc)

    def _relpath(self, path: Path) -> str:
        """Return a path relative to the epic dir when possible."""
        try:
            return str(path.relative_to(self.epic_dir))
        except ValueError:
            return str(path)

    def start_dispatch(
        self,
        *,
        role: str,
        model: str,
        prompt: str,
        conversation_log: Path | None = None,
        input_tokens: int | None = None,
    ) -> DispatchRecord:
        """Record dispatch start and return file paths for this invocation."""
        prompt_hash = compute_prompt_hash(prompt)
        dispatch_id = f"{prompt_hash}-{time.time_ns()}"
        prompt_file = f"dispatches/{prompt_hash}-prompt.txt"
        response_file = f"dispatches/{prompt_hash}-response.txt"

        if conversation_log is None:
            conversation_path = self.dispatches_dir / f"{dispatch_id}-conversation.jsonl"
        else:
            conversation_path = conversation_log
        conversation_file = self._relpath(conversation_path)

        try:
            (self.epic_dir / prompt_file).write_text(prompt, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write prompt file: %s", exc)

        started = DispatchArtifact(
            ts=datetime.now(UTC).isoformat(),
            run_id=self.run_id,
            dispatch_id=dispatch_id,
            status="started",
            role=role,
            model=model,
            prompt_hash=prompt_hash,
            prompt_tokens=input_tokens or estimate_tokens(prompt),
            prompt_file=prompt_file,
            response_file=response_file,
            conversation_file=conversation_file,
        )
        self._append_entry(started.to_dict())

        return DispatchRecord(
            dispatch_id=dispatch_id,
            prompt_hash=prompt_hash,
            prompt_file=prompt_file,
            response_file=response_file,
            conversation_file=conversation_file,
            conversation_path=conversation_path,
        )

    def record(
        self,
        *,
        dispatch: DispatchRecord,
        role: str,
        model: str,
        prompt: str,
        output: str,
        success: bool,
        exit_code: int,
        turns: int | None = None,
        duration_ms: int = 0,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Record a completed dispatch to the unified log.

        Writes the response to content-addressed storage, then appends a
        completion entry linking the dispatch metadata together.

        Args:
            role: Dispatch role (e.g. "planner", "gap_detector", "implementation").
            model: Model identifier (e.g. "opus", "codex").
            prompt: Full prompt text.
            output: Agent response text.
            success: Whether the dispatch succeeded.
            exit_code: Process exit code.
            turns: Number of agent turns (if known).
            duration_ms: Wall-clock duration in milliseconds.
            input_tokens: Actual input token count (from provider). Falls back to estimate.
            output_tokens: Actual output token count (from provider). Falls back to estimate.
        """
        try:
            (self.epic_dir / dispatch.response_file).write_text(output, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write dispatch response file: %s", exc)

        completed = DispatchArtifact(
            ts=datetime.now(UTC).isoformat(),
            run_id=self.run_id,
            dispatch_id=dispatch.dispatch_id,
            status="completed",
            role=role,
            model=model,
            prompt_hash=dispatch.prompt_hash,
            prompt_tokens=input_tokens or estimate_tokens(prompt),
            response_tokens=output_tokens or estimate_tokens(output),
            turns=turns,
            success=success,
            exit_code=exit_code,
            duration_ms=duration_ms,
            prompt_file=dispatch.prompt_file,
            response_file=dispatch.response_file,
            conversation_file=dispatch.conversation_file,
        )

        self._append_entry(completed.to_dict())


@contextmanager
def dispatch_logging(epic_dir: Path, run_id: str):
    """Context manager that activates unified dispatch logging.

    While active, all ``dispatch_agent()`` calls automatically record
    entries to the epic's ``dispatch.jsonl``.

    Usage::

        with dispatch_logging(epic_dir, run_id) as log:
            dispatch_agent(prompt=..., model=..., role=...)
            # ^ automatically recorded

    Args:
        epic_dir: Path to the epic directory.
        run_id: UUID string for this execution run.

    Yields:
        The active DispatchLog instance.
    """
    global _active_dispatch_log
    log = DispatchLog(epic_dir, run_id)
    _active_dispatch_log = log
    try:
        yield log
    finally:
        _active_dispatch_log = None


class DispatchTimer:
    """Simple wall-clock timer for measuring dispatch duration."""

    def __init__(self) -> None:
        self._start: float = 0

    def start(self) -> None:
        self._start = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)


def read_dispatch_log(epic_dir: Path) -> list[dict]:
    """Read all entries from an epic's dispatch.jsonl.

    Args:
        epic_dir: Path to the epic directory.

    Returns:
        List of dispatch entry dicts, in chronological order.
    """
    log_path = epic_dir / "dispatch.jsonl"
    if not log_path.exists():
        return []

    return [entry.to_dict() for entry in read_dispatch_artifacts(epic_dir)]


def read_dispatch_artifacts(epic_dir: Path) -> list[DispatchArtifact]:
    """Read typed dispatch entries from an epic's dispatch.jsonl."""
    log_path = epic_dir / "dispatch.jsonl"
    if not log_path.exists():
        return []

    entries: list[DispatchArtifact] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(DispatchArtifact.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue

    return entries


def token_summary(epic_dir: Path, run_id: str | None = None) -> str:
    """Generate a token usage summary table from dispatch.jsonl.

    Groups dispatches by role and shows aggregate token counts.

    Args:
        epic_dir: Path to the epic directory.
        run_id: Optional run_id filter. If None, includes all runs.

    Returns:
        Formatted text table suitable for console output.
    """
    entries = read_dispatch_artifacts(epic_dir)
    if run_id:
        entries = [entry for entry in entries if entry.run_id == run_id]
    entries = [entry for entry in entries if entry.status == "completed"]

    if not entries:
        return "No dispatch entries found."

    # Aggregate by role
    roles: dict[str, dict] = {}
    for entry in entries:
        role = entry.role
        if role not in roles:
            roles[role] = {
                "dispatches": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "duration_ms": 0,
            }
        agg = roles[role]
        agg["dispatches"] += 1
        agg["input_tokens"] += entry.prompt_tokens
        agg["output_tokens"] += entry.response_tokens or 0
        agg["duration_ms"] += entry.duration_ms or 0

    # Format table
    lines = [
        f"{'Role':<25} {'Dispatches':>10} {'Input tokens':>14} {'Output tokens':>14} {'Duration':>10}",
        "-" * 77,
    ]

    total_dispatches = 0
    total_input = 0
    total_output = 0
    total_duration = 0

    for role, agg in sorted(roles.items()):
        duration_s = agg["duration_ms"] / 1000
        lines.append(
            f"{role:<25} {agg['dispatches']:>10,} {agg['input_tokens']:>14,} "
            f"{agg['output_tokens']:>14,} {duration_s:>9.1f}s"
        )
        total_dispatches += agg["dispatches"]
        total_input += agg["input_tokens"]
        total_output += agg["output_tokens"]
        total_duration += agg["duration_ms"]

    lines.append("-" * 77)
    total_duration_s = total_duration / 1000
    lines.append(
        f"{'TOTAL':<25} {total_dispatches:>10,} {total_input:>14,} "
        f"{total_output:>14,} {total_duration_s:>9.1f}s"
    )

    return "\n".join(lines)
