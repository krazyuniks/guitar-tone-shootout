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
# Turn defaults per agent type
# ---------------------------------------------------------------------------

TURN_DEFAULTS: dict[str, int] = {
    "planning": 50,
    "architecture": 30,
    "implementation": 40,
    "validation": 15,
    "regression": 30,
    "gap_detection": 30,
    "critique_plan": 20,
    "critique_story": 15,
    "critique_epic": 20,
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
    turns: int | None = None


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
        json_schema: dict | None,
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
        json_schema: dict | None,
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
            "--no-session-persistence",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]

        # --tools "" disables all tools; comma-separated list restricts to named tools
        args.extend(["--tools", ",".join(tools)])

        if json_schema:
            args.extend(["--json-schema", json.dumps(json_schema)])

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
        turns = None

        if raw.strip():
            try:
                parsed = json.loads(raw)
                structured_output = parsed

                if isinstance(parsed, dict):
                    turns = parsed.get("num_turns") or parsed.get("turns")
                    # Extract the agent's text response as the primary output
                    if "result" in parsed and isinstance(parsed["result"], str):
                        output = parsed["result"]
            except json.JSONDecodeError:
                # Raw text output — not structured
                pass

        return AgentResult(
            success=success,
            output=output,
            structured_output=structured_output,
            exit_code=exit_code,
            turns=turns,
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
        json_schema: dict | None,  # noqa: ARG002
        no_mcp: bool = False,  # noqa: ARG002
    ) -> list[str]:
        """Build Codex CLI arguments. Prompt is piped via stdin by the caller.

        Codex CLI does not support --tools or --max-turns flags. Those
        parameters are accepted for interface compatibility but are not
        passed to the CLI.
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
        turns = None

        # Parse --json stdout for metadata
        if raw.strip():
            try:
                parsed = json.loads(raw)
                structured_output = parsed
                if isinstance(parsed, dict):
                    turns = parsed.get("num_turns") or parsed.get("turns")
                    # If -o file was empty, try extracting from JSON
                    if not output and "result" in parsed:
                        output = str(parsed["result"])
            except json.JSONDecodeError:
                # Raw text — use as output if -o file was empty
                if not output:
                    output = raw

        return AgentResult(
            success=success,
            output=output,
            structured_output=structured_output,
            exit_code=exit_code,
            turns=turns,
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
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
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
        json_schema: JSON schema for structured output (optional).
        cwd: Working directory for the subprocess.
        adapter: Provider adapter (auto-selected from model if None).
        no_mcp: If True, pass --no-mcp to skip MCP server startup.
        conversation_log: Path to write per-dispatch conversation JSONL.
            When provided, enables streaming Popen mode with full
            transcript capture.

    Returns:
        AgentResult with success status, output, and turn count.
    """
    if adapter is None:
        adapter = get_adapter(model)

    # Log dispatch metadata
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)

    logger.info(
        "Dispatching agent: model=%s, tools=%s, max_turns=%d, "
        "json_schema=%s, prompt_hash=%s, prompt_tokens=%d",
        model,
        tools,
        max_turns,
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
        json_schema=json_schema,
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
        "Agent complete: success=%s, exit_code=%d, turns=%s",
        result.success,
        result.exit_code,
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


def get_default_turns(agent_type: str) -> int:
    """Get default max_turns for an agent type.

    Args:
        agent_type: One of "planning", "architecture", "implementation",
            "validation", "regression", "critique_plan", "critique_story",
            "critique_epic".

    Returns:
        Default max_turns for the agent type.
    """
    return TURN_DEFAULTS.get(agent_type, TURN_DEFAULTS["implementation"])


def get_tools_for_role(role: str) -> list[str]:
    """Get the tool restriction list for an agent role.

    Args:
        role: One of "implementation", "validation_browser",
            "validation_api", "regression", "critique".

    Returns:
        List of tool name strings.
    """
    return list(TOOL_SETS.get(role, TOOL_SETS["implementation"]))
