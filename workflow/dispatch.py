"""Agent dispatch module with multi-provider support.

Dispatches prompts to AI coding agents via adapter classes. Supports
Claude Code (ClaudeAdapter) and OpenAI Codex CLI (CodexAdapter).
Adapter selection is automatic based on model name.

No dependency on run_epic.py or any V1 code.
"""

import contextlib
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Budget defaults per agent type (Section 8.2 Strategy 7)
# ---------------------------------------------------------------------------

BUDGET_DEFAULTS: dict[str, dict[str, int | float]] = {
    "planning": {"max_turns": 50, "max_budget_usd": 5.00},
    "architecture": {"max_turns": 30, "max_budget_usd": 3.00},
    "implementation": {"max_turns": 40, "max_budget_usd": 4.00},
    "validation": {"max_turns": 15, "max_budget_usd": 0.50},
    "regression": {"max_turns": 30, "max_budget_usd": 3.00},
    "gap_detection": {"max_turns": 30, "max_budget_usd": 3.00},
    "critique_plan": {"max_turns": 20, "max_budget_usd": 5.00},
    "critique_story": {"max_turns": 15, "max_budget_usd": 3.00},
    "critique_epic": {"max_turns": 20, "max_budget_usd": 8.00},
}

# Fallback models per primary model (Section 8.6 Decision 6)
FALLBACK_MODELS: dict[str, str] = {
    "opus": "sonnet",
    "sonnet": "haiku",
    "haiku": "haiku",  # no cheaper fallback
    "codex": "codex",  # no fallback — single provider
}

# Tool restrictions per agent role (Section 8.2 Strategy 4)
TOOL_SETS: dict[str, list[str]] = {
    "planning": ["Read", "Bash", "Glob", "Grep"],
    "implementation": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "validation_browser": ["Read", "Bash", "Glob", "Grep"],
    "validation_api": ["Bash", "Read", "Glob", "Grep"],
    "regression": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "critique": ["Read", "Bash", "Glob", "Grep"],
}


# ---------------------------------------------------------------------------
# AgentResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result of an agent dispatch invocation."""

    success: bool
    output: str
    structured_output: dict | None = None
    exit_code: int = 0
    cost_usd: float | None = None
    turns: int | None = None
    is_overload_or_transient: bool = False


# ---------------------------------------------------------------------------
# AgentAdapter protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol for agent CLI adapters."""

    @property
    def name(self) -> str: ...

    def build_args(
        self,
        model: str,
        tools: list[str],
        max_turns: int,
        max_budget_usd: float,
        json_schema: dict | None,
        fallback_model: str | None = None,
        no_mcp: bool = False,
    ) -> list[str]: ...

    def parse_result(
        self,
        completed: subprocess.CompletedProcess,
    ) -> "AgentResult": ...


# ---------------------------------------------------------------------------
# ClaudeAdapter
# ---------------------------------------------------------------------------


class ClaudeAdapter:
    """Claude Code CLI adapter.

    Passes prompt via stdin (-p -) to avoid OS argument length limits.
    Model, tools, and skills are passed as individual CLI flags.
    MCP servers are managed globally via Claude Code's own configuration.
    """

    @property
    def name(self) -> str:
        return "claude"

    def build_args(
        self,
        model: str,
        tools: list[str],
        max_turns: int,
        max_budget_usd: float,
        json_schema: dict | None,
        fallback_model: str | None = None,
        no_mcp: bool = False,
    ) -> list[str]:
        """Build CLI arguments. Prompt is piped via stdin by the caller."""
        args = [
            "claude",
            "-p",
            "-",
            "--model",
            model,
            "--max-turns",
            str(max_turns),
            "--max-budget-usd",
            str(max_budget_usd),
            "--no-session-persistence",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]

        # --tools "" disables all tools; comma-separated list restricts to named tools
        args.extend(["--tools", ",".join(tools)])

        if json_schema:
            args.extend(["--json-schema", json.dumps(json_schema)])

        if fallback_model and fallback_model != model:
            args.extend(["--fallback-model", fallback_model])

        if no_mcp:
            args.extend(["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'])

        return args

    def parse_result(
        self,
        completed: subprocess.CompletedProcess,
    ) -> AgentResult:
        """Parse Claude Code JSON output into AgentResult.

        Claude Code --output-format json emits:
        {"type":"result","subtype":"success","is_error":false,
         "duration_ms":N,"duration_api_ms":N,"num_turns":N,
         "result":"the agent's text response"}

        The agent's text response is extracted as `output`.
        The full envelope is kept as `structured_output`.
        """
        raw = completed.stdout or ""
        exit_code = completed.returncode
        success = exit_code == 0

        output = raw
        structured_output = None
        cost_usd = None
        turns = None

        if raw.strip():
            try:
                parsed = json.loads(raw)
                structured_output = parsed

                if isinstance(parsed, dict):
                    cost_usd = parsed.get("cost_usd")
                    turns = parsed.get("num_turns") or parsed.get("turns")
                    # Extract the agent's text response as the primary output
                    if "result" in parsed and isinstance(parsed["result"], str):
                        output = parsed["result"]
            except json.JSONDecodeError:
                # Raw text output — not structured
                pass

        # Detect overload/transient failures
        is_transient = _is_overload_or_transient(exit_code, raw, completed.stderr or "")

        return AgentResult(
            success=success,
            output=output,
            structured_output=structured_output,
            exit_code=exit_code,
            cost_usd=cost_usd,
            turns=turns,
            is_overload_or_transient=is_transient,
        )


# ---------------------------------------------------------------------------
# CodexAdapter
# ---------------------------------------------------------------------------


class CodexAdapter:
    """OpenAI Codex CLI adapter.

    Passes prompt via stdin (codex exec reads stdin when no prompt arg given).
    Uses --json for structured output, --ephemeral for no session persistence.
    MCP servers are configured globally in ~/.codex/config.toml.

    Sandbox modes:
    - "read-only" for critique (read codebase, no writes)
    - "danger-full-access" for implementation (full write access)
    """

    def __init__(self, sandbox: str = "read-only") -> None:
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        return "codex"

    @staticmethod
    def _find_binary() -> str:
        """Locate the codex binary."""
        path = shutil.which("codex")
        if path:
            return path
        volta_path = Path.home() / ".volta" / "bin" / "codex"
        if volta_path.exists():
            return str(volta_path)
        return "codex"  # fall through to PATH

    def build_args(
        self,
        model: str,  # noqa: ARG002
        tools: list[str],  # noqa: ARG002
        max_turns: int,  # noqa: ARG002
        max_budget_usd: float,  # noqa: ARG002
        json_schema: dict | None,  # noqa: ARG002
        fallback_model: str | None = None,  # noqa: ARG002
        no_mcp: bool = False,  # noqa: ARG002
    ) -> list[str]:
        """Build Codex CLI arguments. Prompt is piped via stdin by the caller.

        Codex CLI does not support --tools, --max-turns, --max-budget-usd,
        or --fallback-model flags. Those parameters are accepted for
        interface compatibility but are not passed to the CLI.
        """
        binary = self._find_binary()

        # Create a temp file for -o output capture before building args.
        # Create a temp file for -o output capture. parse_result extracts
        # the path from completed.args rather than reading instance state,
        # so sequential dispatches on a shared adapter can't clobber.
        fd, output_path = tempfile.mkstemp(suffix=".txt", prefix="codex-output-")
        os.close(fd)

        args = [
            binary,
            "exec",
            "--model",
            "gpt-5.3-codex",
            "-c",
            "model_reasoning_effort=high",
            "--ephemeral",
            "--json",
            "--sandbox",
            self._sandbox,
            "-o",
            output_path,
        ]

        return args

    def parse_result(
        self,
        completed: subprocess.CompletedProcess,
    ) -> "AgentResult":
        """Parse Codex CLI output into AgentResult.

        Codex --json emits structured JSON to stdout with cost/turns info.
        The -o flag captures the last assistant message to a file.
        The output path is extracted from the subprocess args to avoid
        reliance on instance state (which could be clobbered by sequential
        dispatches on a shared adapter).
        """
        raw = completed.stdout or ""
        exit_code = completed.returncode
        success = exit_code == 0

        # Extract -o output path from the args used for this invocation
        output = ""
        output_path_str = None
        args = completed.args if isinstance(completed.args, list) else []
        for i, arg in enumerate(args):
            if arg == "-o" and i + 1 < len(args):
                output_path_str = args[i + 1]
                break

        if output_path_str:
            output_path = Path(output_path_str)
            try:
                if output_path.exists():
                    output = output_path.read_text(encoding="utf-8")
            finally:
                with contextlib.suppress(OSError):
                    output_path.unlink(missing_ok=True)

        structured_output = None
        cost_usd = None
        turns = None

        # Parse --json stdout for metadata
        if raw.strip():
            try:
                parsed = json.loads(raw)
                structured_output = parsed
                if isinstance(parsed, dict):
                    cost_usd = parsed.get("cost_usd")
                    turns = parsed.get("num_turns") or parsed.get("turns")
                    # If -o file was empty, try extracting from JSON
                    if not output and "result" in parsed:
                        output = str(parsed["result"])
            except json.JSONDecodeError:
                # Raw text — use as output if -o file was empty
                if not output:
                    output = raw

        # Detect overload/transient failures
        is_transient = _is_overload_or_transient(exit_code, raw, completed.stderr or "")

        return AgentResult(
            success=success,
            output=output,
            structured_output=structured_output,
            exit_code=exit_code,
            cost_usd=cost_usd,
            turns=turns,
            is_overload_or_transient=is_transient,
        )


# ---------------------------------------------------------------------------
# Adapter routing
# ---------------------------------------------------------------------------

_claude_adapter = ClaudeAdapter()
_codex_critique_adapter = CodexAdapter(sandbox="read-only")
_codex_impl_adapter = CodexAdapter(sandbox="danger-full-access")

ADAPTER_MAP: dict[str, AgentAdapter] = {
    "opus": _claude_adapter,
    "sonnet": _claude_adapter,
    "haiku": _claude_adapter,
    "codex": _codex_critique_adapter,  # default to read-only for safety
}


def get_adapter(model: str) -> AgentAdapter:
    """Return the appropriate adapter for a model name.

    Args:
        model: Model identifier (e.g. "opus", "sonnet", "codex").

    Returns:
        The adapter instance for the given model.
    """
    adapter = ADAPTER_MAP.get(model)
    if adapter is None:
        logger.warning("Unknown model '%s', falling back to Claude adapter", model)
        return _claude_adapter
    return adapter


def get_codex_adapter(sandbox: str = "read-only") -> CodexAdapter:
    """Return a CodexAdapter with the specified sandbox mode.

    Args:
        sandbox: "read-only" for critique, "danger-full-access" for implementation.

    Returns:
        CodexAdapter instance.
    """
    if sandbox == "read-only":
        return _codex_critique_adapter
    return _codex_impl_adapter


# ---------------------------------------------------------------------------
# Transient failure detection
# ---------------------------------------------------------------------------


def _is_overload_or_transient(exit_code: int, stdout: str, stderr: str) -> bool:
    """Determine if a dispatch failure is overload or transient.

    Transient failures include HTTP 529 (overload), network errors,
    5xx server errors, and timeouts. These should be retried with
    a fallback model/provider without consuming the story retry budget.

    Args:
        exit_code: Process exit code.
        stdout: Process stdout.
        stderr: Process stderr.

    Returns:
        True if the failure appears to be transient/overload.
    """
    combined = (stdout + stderr).lower()

    transient_patterns = [
        "529",
        "overloaded",
        "rate limit",
        "rate_limit",
        "too many requests",
        "connection refused",
        "connection reset",
        "connection timed out",
        "network error",
        "network unreachable",
        "dns resolution",
        "timeout",
        "timed out",
        "503 service unavailable",
        "502 bad gateway",
        "500 internal server error",
        "econnrefused",
        "econnreset",
        "etimedout",
        "ehostunreach",
        "enetunreach",
    ]

    return any(pattern in combined for pattern in transient_patterns)


# ---------------------------------------------------------------------------
# Prompt metadata helpers
# ---------------------------------------------------------------------------


def _log_dispatch_prompt(prompt: str, prompt_hash: str, model: str) -> None:
    """Write the full prompt text to the logs directory for debugging.

    Creates .planning/epics/logs/ if needed. Each dispatch writes a
    timestamped file so failed agents can be debugged after the fact.
    """
    logs_dir = PROJECT_ROOT / ".planning" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = logs_dir / f"dispatch-{model}-{prompt_hash}-{ts}.txt"
    try:
        path.write_text(prompt, encoding="utf-8")
        logger.debug("Prompt logged to %s", path)
    except OSError as exc:
        logger.warning("Failed to write dispatch prompt log: %s", exc)


def compute_prompt_hash(prompt: str) -> str:
    """Compute a short hash of the prompt text for JSONL logging.

    Args:
        prompt: The full prompt text.

    Returns:
        First 12 characters of the SHA-256 hex digest.
    """
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (4 chars per token).

    This is a fast approximation for logging purposes. The actual
    token count depends on the model's tokeniser.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Approximate token count.
    """
    return len(text) // 4


# ---------------------------------------------------------------------------
# Core dispatch function
# ---------------------------------------------------------------------------


def dispatch_agent(
    prompt: str,
    model: str,
    tools: list[str],
    max_turns: int = 30,
    max_budget_usd: float = 3.0,
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
    fallback_model: str | None = None,
    adapter: AgentAdapter | None = None,
    no_mcp: bool = False,
    conversation_log: Path | None = None,
) -> AgentResult:
    """Dispatch a prompt to an agent and return the structured result.

    Constructs CLI arguments via the adapter, runs the subprocess,
    and parses the result into an AgentResult. Logs dispatch metadata
    (model, prompt_hash, prompt_tokens).

    When ``conversation_log`` is provided, uses ``subprocess.Popen`` with
    line-by-line stdout reading and a ConversationLogger for full transcript
    capture. Stderr is redirected to a tempfile to prevent pipe deadlocks.

    Args:
        prompt: The full agent prompt text.
        model: Model identifier (e.g. "opus", "sonnet", "haiku", "codex").
        tools: List of tool names the agent may use.
        max_turns: Maximum conversation turns.
        max_budget_usd: Dollar cap for this invocation.
        json_schema: JSON schema for structured output (optional).
        cwd: Working directory for the subprocess.
        fallback_model: Model to fall back to on HTTP 529 overload.
        adapter: Provider adapter (auto-selected from model if None).
        no_mcp: If True, pass --no-mcp to skip MCP server startup.
        conversation_log: Path to write per-dispatch conversation JSONL.
            When provided, enables streaming Popen mode with full
            transcript capture.

    Returns:
        AgentResult with success status, output, cost, and turn count.
    """
    if adapter is None:
        adapter = get_adapter(model)

    # Resolve fallback model from defaults if not provided
    if fallback_model is None:
        fallback_model = FALLBACK_MODELS.get(model)

    # Log dispatch metadata
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)

    logger.info(
        "Dispatching agent: model=%s, tools=%s, max_turns=%d, "
        "max_budget=$%.2f, json_schema=%s, prompt_hash=%s, prompt_tokens=%d",
        model,
        tools,
        max_turns,
        max_budget_usd,
        bool(json_schema),
        prompt_hash,
        prompt_tokens,
    )

    # Write prompt to logs dir for post-mortem debugging
    _log_dispatch_prompt(prompt, prompt_hash, model)

    args = adapter.build_args(
        model=model,
        tools=tools,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        fallback_model=fallback_model,
        no_mcp=no_mcp,
    )

    # Clear CLAUDECODE env var to allow nested dispatch from within a Claude session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    if conversation_log is not None:
        # Streaming mode: Popen with line-by-line reading + conversation logger.
        # Stderr goes to a tempfile to prevent pipe buffer deadlock.
        result = _dispatch_streaming(
            args=args,
            prompt=prompt,
            model=model,
            adapter=adapter,
            env=env,
            cwd=cwd,
            conversation_log=conversation_log,
        )
    else:
        # Simple mode: subprocess.run (no conversation logging)
        result = _dispatch_simple(
            args=args,
            prompt=prompt,
            adapter=adapter,
            env=env,
            cwd=cwd,
        )

    logger.info(
        "Agent complete: success=%s, exit_code=%d, cost=$%s, turns=%s",
        result.success,
        result.exit_code,
        result.cost_usd or "unknown",
        result.turns or "unknown",
    )

    return result


def _dispatch_simple(
    args: list[str],
    prompt: str,
    adapter: AgentAdapter,
    env: dict,
    cwd: Path,
) -> AgentResult:
    """Run agent via subprocess.run (no streaming, no conversation logging)."""
    try:
        completed = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=600,  # 10 minute timeout
        )
    except subprocess.TimeoutExpired:
        logger.warning("Agent dispatch timed out after 600s")
        return AgentResult(
            success=False,
            output="",
            exit_code=-1,
            is_overload_or_transient=True,
        )

    # Log stderr for debugging dispatch failures
    if completed.returncode != 0 and completed.stderr:
        logger.warning("Agent stderr: %s", completed.stderr[:500])

    return adapter.parse_result(completed)


def _dispatch_streaming(
    args: list[str],
    prompt: str,
    model: str,
    adapter: AgentAdapter,
    env: dict,
    cwd: Path,
    conversation_log: Path,
) -> AgentResult:
    """Run agent via Popen with line-by-line stdout reading + conversation logger.

    Stderr is redirected to a tempfile to prevent pipe buffer deadlock.
    """
    from workflow.conversation_logger import ConversationLogger

    stdout_lines: list[str] = []

    with (
        tempfile.TemporaryFile(mode="w+") as stderr_tmp,
        ConversationLogger(conversation_log, adapter.name, model) as conv_logger,
    ):
        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_tmp,
                text=True,
                cwd=cwd,
                env=env,
            )
        except OSError as exc:
            logger.error("Failed to start agent process: %s", exc)
            return AgentResult(
                success=False,
                output=f"Failed to start process: {exc}",
                exit_code=-1,
            )

        # Write prompt to stdin and close it
        if process.stdin is not None:
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except OSError as exc:
                logger.warning("Failed to write prompt to stdin: %s", exc)

        # Read stdout line by line, feeding to conversation logger
        if process.stdout is not None:
            for line in process.stdout:
                stdout_lines.append(line)
                conv_logger.process_line(line)

        process.wait()

        # Read stderr from the tempfile (safe — process is done)
        stderr_tmp.seek(0)
        stderr_output = stderr_tmp.read()

    exit_code = process.returncode
    stdout_output = "".join(stdout_lines)

    if exit_code != 0 and stderr_output:
        logger.warning("Agent stderr: %s", stderr_output[:500])

    # Create a CompletedProcess for the adapter to parse
    completed = subprocess.CompletedProcess(
        args=args,
        returncode=exit_code,
        stdout=stdout_output,
        stderr=stderr_output,
    )

    return adapter.parse_result(completed)


def dispatch_with_fallback(
    prompt: str,
    primary_model: str,
    fallback_model: str,
    tools: list[str],
    max_turns: int = 30,
    max_budget_usd: float = 3.0,
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
    adapter: AgentAdapter | None = None,
    no_mcp: bool = False,
    conversation_log: Path | None = None,
) -> AgentResult:
    """Dispatch with orchestrator-level retry for transient provider failures.

    This is distinct from the story-level retry budget. Transient provider
    failures (overload, network errors, 5xx) should not consume retry
    attempts that are reserved for implementation failures.

    The flow:
    1. Dispatch with primary_model (which also sets --fallback-model for
       HTTP 529 handled by Claude Code itself).
    2. If the result is successful, return it.
    3. If the failure is transient (overload, network, 5xx), retry once
       with the fallback_model.
    4. If the failure is not transient, return it unchanged (real failure).

    Args:
        prompt: The full agent prompt text.
        primary_model: Primary model to try first.
        fallback_model: Model to use on transient failure retry.
        tools: List of tool names.
        max_turns: Maximum turns.
        max_budget_usd: Dollar cap.
        json_schema: Structured output schema.
        cwd: Working directory.
        adapter: Provider adapter.
        no_mcp: If True, pass --no-mcp to skip MCP server startup.

    Returns:
        AgentResult from either the primary or fallback dispatch.
    """
    # Primary dispatch
    result = dispatch_agent(
        prompt=prompt,
        model=primary_model,
        tools=tools,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        cwd=cwd,
        fallback_model=fallback_model,
        adapter=adapter,
        no_mcp=no_mcp,
        conversation_log=conversation_log,
    )

    if result.success:
        return result

    # Check if failure is transient
    if not result.is_overload_or_transient:
        return result  # Real failure — don't retry

    logger.warning(
        "Primary dispatch failed with transient error (model=%s). Retrying with fallback model=%s",
        primary_model,
        fallback_model,
    )

    # Fallback dispatch — no further fallback model
    fallback_result = dispatch_agent(
        prompt=prompt,
        model=fallback_model,
        tools=tools,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        cwd=cwd,
        fallback_model=None,  # No further fallback
        adapter=adapter,
        no_mcp=no_mcp,
        conversation_log=conversation_log,
    )

    return fallback_result


# ---------------------------------------------------------------------------
# Convenience helpers for dispatch metadata
# ---------------------------------------------------------------------------


def get_dispatch_metadata(
    prompt: str,
    model: str,
    adapter_name: str = "claude",
) -> dict:
    """Build metadata dict suitable for JSONL agent_dispatched events.

    Args:
        prompt: The prompt text.
        model: Model identifier.
        adapter_name: Adapter name ("claude" or "codex").

    Returns:
        Dict with model, adapter, prompt_hash, prompt_tokens.
    """
    return {
        "model": model,
        "adapter": adapter_name,
        "prompt_hash": compute_prompt_hash(prompt),
        "prompt_tokens": estimate_tokens(prompt),
    }


def get_budget_defaults(agent_type: str) -> dict[str, int | float]:
    """Get default max_turns and max_budget_usd for an agent type.

    Args:
        agent_type: One of "planning", "architecture", "implementation",
            "validation", "regression", "critique_plan", "critique_story",
            "critique_epic".

    Returns:
        Dict with "max_turns" (int) and "max_budget_usd" (float).
    """
    return dict(BUDGET_DEFAULTS.get(agent_type, BUDGET_DEFAULTS["implementation"]))


def get_tools_for_role(role: str) -> list[str]:
    """Get the tool restriction list for an agent role.

    Args:
        role: One of "implementation", "validation_browser",
            "validation_api", "regression", "critique".

    Returns:
        List of tool name strings.
    """
    return list(TOOL_SETS.get(role, TOOL_SETS["implementation"]))
