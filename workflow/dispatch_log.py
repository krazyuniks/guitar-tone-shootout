"""Unified dispatch logging with prompt/response pairing and token tracking.

Centralises all dispatch logging into a single JSONL file per epic run
with content-addressed prompt/response storage. Replaces the scattered
ad-hoc file writing (_log_dispatch_prompt, codex-response-*, last-planner-output).

Each dispatch_agent() call is automatically recorded when a DispatchLog
is active via the dispatch_logging() context manager.

Reference: GitHub issue #153.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime

from workflow.dispatch import compute_prompt_hash, estimate_tokens

logger = logging.getLogger(__name__)

# Module-level active dispatch log — set by dispatch_logging() context manager.
# dispatch_agent() checks this and records entries automatically.
_active_dispatch_log: DispatchLog | None = None


def get_active_dispatch_log() -> DispatchLog | None:
    """Return the currently active dispatch log, or None."""
    return _active_dispatch_log


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

    def record(
        self,
        *,
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

        Writes the prompt and response to content-addressed files, then
        appends a JSONL entry linking them together with metadata.

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
        prompt_hash = compute_prompt_hash(prompt)

        # Content-addressed prompt storage (idempotent — same hash = same file)
        prompt_file = f"dispatches/{prompt_hash}-prompt.txt"
        response_file = f"dispatches/{prompt_hash}-response.txt"

        try:
            (self.epic_dir / prompt_file).write_text(prompt, encoding="utf-8")
            (self.epic_dir / response_file).write_text(output, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write dispatch files: %s", exc)

        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "role": role,
            "model": model,
            "prompt_hash": prompt_hash,
            "prompt_tokens": input_tokens or estimate_tokens(prompt),
            "response_tokens": output_tokens or estimate_tokens(output),
            "turns": turns,
            "success": success,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "prompt_file": prompt_file,
            "response_file": response_file,
        }

        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
                f.flush()
        except OSError as exc:
            logger.warning("Failed to write dispatch log entry: %s", exc)


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

    entries: list[dict] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
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
    entries = read_dispatch_log(epic_dir)
    if run_id:
        entries = [e for e in entries if e.get("run_id") == run_id]

    if not entries:
        return "No dispatch entries found."

    # Aggregate by role
    roles: dict[str, dict] = {}
    for entry in entries:
        role = entry.get("role", "unknown")
        if role not in roles:
            roles[role] = {
                "dispatches": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "duration_ms": 0,
            }
        agg = roles[role]
        agg["dispatches"] += 1
        agg["input_tokens"] += entry.get("prompt_tokens", 0)
        agg["output_tokens"] += entry.get("response_tokens", 0)
        agg["duration_ms"] += entry.get("duration_ms", 0)

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
