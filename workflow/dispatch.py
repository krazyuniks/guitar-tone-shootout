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
import select
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rich.console import Console

from workflow.artifacts import DispatchResultArtifact

if TYPE_CHECKING:
    from workflow.epic_config import EpicConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Turn defaults per agent type
# ---------------------------------------------------------------------------


# Compatibility alias while callers migrate to the typed artifact name.
AgentResult = DispatchResultArtifact


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
        json_schema: dict | None,
        mcp_servers: list[str] | None = None,
        streaming: bool = False,
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
        json_schema: dict | None,
        mcp_servers: list[str] | None = None,
        streaming: bool = False,
    ) -> list[str]:
        """Build CLI arguments. Prompt is piped via stdin by the caller."""
        from workflow.mcp import build_mcp_config

        args = [
            "claude",
            "-p",
            "-",
            "--model",
            model,
            "--no-session-persistence",
            "--output-format",
            "stream-json" if streaming else "json",
            "--dangerously-skip-permissions",
        ]

        if streaming:
            args.append("--verbose")

        if json_schema:
            args.extend(["--json-schema", json.dumps(json_schema)])

        # Always pass --strict-mcp-config with the resolved config.
        # None or empty list → no MCP servers (same as old no_mcp=True).
        mcp_config = build_mcp_config(mcp_servers or [])
        args.extend(["--strict-mcp-config", "--mcp-config", mcp_config])

        return args

    def parse_result(
        self,
        completed: subprocess.CompletedProcess,
    ) -> AgentResult:
        """Parse Claude Code JSON output into AgentResult.

        Claude Code ``--output-format json`` emits an envelope::

            {"type":"result","subtype":"success","is_error":false,
             "duration_ms":N,"duration_api_ms":N,"num_turns":N,
             "result":"the agent's text response",
             "structured_output": ...}

        Without ``--json-schema``, the agent's text lives in ``result``.

        With ``--json-schema``, the constrained JSON object is in
        ``structured_output``. Some Claude runs still populate ``result``
        with a prose summary after successfully calling StructuredOutput,
        so ``structured_output`` must take precedence whenever present.
        We serialise it back to a JSON string so callers can use
        ``extract_json_from_text(output)`` uniformly.
        """
        raw = completed.stdout or ""
        exit_code = completed.returncode
        success = exit_code == 0

        output = raw
        structured_output = None
        turns = None

        parsed = _extract_json_payload(raw)
        if parsed is not None:
            schema_output = parsed.get("structured_output")
            structured_output = schema_output if isinstance(schema_output, dict) else parsed
            turns = parsed.get("num_turns") or parsed.get("turns")
            result_text = parsed.get("result")

            if schema_output is not None:
                # --json-schema mode: prefer structured_output even if the CLI
                # also appends a prose summary in "result".
                output = json.dumps(schema_output)
            elif isinstance(result_text, str) and result_text:
                # Normal mode: text response in "result"
                output = result_text
            else:
                # Failure envelopes such as error_max_structured_output_retries still
                # carry useful diagnostics; surface them instead of the entire raw stream.
                output = json.dumps(parsed)
        else:
            logger.warning("parse_result: raw stdout is empty or unparseable (exit_code=%d)", exit_code)

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
    Model, approval policy, sandbox, and MCP servers are configured globally
    in ~/.codex/config.toml — the adapter does not override them.
    """

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
        json_schema: dict | None,  # noqa: ARG002
        mcp_servers: list[str] | None = None,  # noqa: ARG002
        streaming: bool = False,  # noqa: ARG002
    ) -> list[str]:
        """Build Codex CLI arguments. Prompt is piped via stdin by the caller."""
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
            "--dangerously-bypass-approvals-and-sandbox",
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
        parsed = _extract_json_payload(raw)
        if parsed is not None:
            structured_output = parsed
            turns = parsed.get("num_turns") or parsed.get("turns")
            # If -o file was empty, try extracting from JSON
            if not output and "result" in parsed:
                output = str(parsed["result"])
        elif not output:
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
_codex_adapter = CodexAdapter()

ADAPTER_MAP: dict[str, AgentAdapter] = {
    "opus": _claude_adapter,
    "sonnet": _claude_adapter,
    "haiku": _claude_adapter,
    "codex": _codex_adapter,
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


def get_codex_adapter() -> CodexAdapter:
    """Return the shared CodexAdapter instance.

    Sandbox and approval policy are controlled by ~/.codex/config.toml.
    """
    return _codex_adapter


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------


def _extract_json_payload(raw: str) -> dict | None:
    """Parse JSON or newline-delimited JSON and return the terminal payload."""
    if not raw.strip():
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    payloads: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed_line = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_line, dict):
            payloads.append(parsed_line)

    if not payloads:
        return None

    for payload in reversed(payloads):
        if payload.get("type") == "result":
            return payload
        if "structured_output" in payload or "result" in payload:
            return payload

    return payloads[-1]


def _extract_last_json_object(raw: str) -> dict | None:
    """Extract the last JSON object embedded anywhere in a string."""
    decoder = json.JSONDecoder()
    payloads: list[dict] = []

    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)

    if not payloads:
        return None
    return payloads[-1]


def _unwrap_structured_output_candidate(payload: object) -> dict | None:
    """Return a likely structured-output payload, unwrapping common envelopes.

    Claude's StructuredOutput tool sometimes receives ``{"result": {...}}`` or a
    similar singleton envelope instead of the schema object itself. This helper
    unwraps that shape so downstream typed parsing can still validate the
    recovered object.
    """
    if not isinstance(payload, dict):
        return None

    if len(payload) == 1:
        key, value = next(iter(payload.items()))
        if key in {"result", "output", "plan", "curation", "data"} and isinstance(value, dict):
            return value
        if key in {"$schema", "schema"} and isinstance(value, str):
            return _extract_last_json_object(value)

    return payload


def _recover_structured_output_from_conversation(conversation_log: Path) -> dict | None:
    """Recover the latest StructuredOutput tool payload from a conversation log."""
    if not conversation_log.is_file():
        return None

    entries: list[dict] = []
    for raw_line in conversation_log.read_text(encoding="utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entries.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue

    for entry in reversed(entries):
        payload = entry.get("payload", {})
        if payload.get("type") != "assistant":
            continue
        message = payload.get("message", {})
        for item in reversed(message.get("content", [])):
            if item.get("type") != "tool_use" or item.get("name") != "StructuredOutput":
                continue
            recovered = _unwrap_structured_output_candidate(item.get("input"))
            if recovered is not None:
                return recovered

    return None


def _is_structured_output_retry_failure(raw_stdout: str) -> bool:
    """Return True when Claude failed only after exhausting structured-output retries."""
    parsed = _extract_json_payload(raw_stdout)
    if not isinstance(parsed, dict):
        return False
    if parsed.get("type") != "result":
        return False
    if parsed.get("subtype") != "error_max_structured_output_retries":
        return False
    errors = parsed.get("errors")
    return isinstance(errors, list) and any(
        "structured output" in str(error).lower() for error in errors
    )


def extract_json_from_text(text: str) -> dict:
    """Extract a JSON object from agent output that may contain surrounding text.

    Tries, in order:
    1. Strip markdown code fences and parse directly
    2. Find the outermost { ... } and parse that

    Raises ValueError if no valid JSON object can be found.
    """
    cleaned = text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()

    # Direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Find outermost { ... } in the original text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON object found in: {text[:200]}")


# JSON schemas for critique responses
STORY_CRITIQUE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["pass", "fail"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {},
                    "issue": {"type": "string"},
                    "convention_violated": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "major"]},
                },
                "required": ["file", "issue", "severity"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["status", "findings", "summary"],
}

EPIC_CRITIQUE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["pass", "fail"]},
        "findings": {"type": "array"},
        "summary": {"type": "string"},
    },
    "required": ["status", "findings", "summary"],
}


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
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
    adapter: AgentAdapter | None = None,
    mcp_servers: list[str] | None = None,
    timeout: int = 600,
    conversation_log: Path | None = None,
    role: str = "agent",
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
        json_schema: JSON schema for structured output (optional).
        cwd: Working directory for the subprocess.
        adapter: Provider adapter (auto-selected from model if None).
        mcp_servers: MCP server names to include. None or empty = no MCP.
        timeout: Subprocess timeout in seconds. 0 = no timeout.
        conversation_log: Path to write per-dispatch conversation JSONL.
            When provided, enables streaming Popen mode with full
            transcript capture.
        role: Human-readable role label for log lines (e.g. "gap_detector",
            "critique", "implementation"). Defaults to "agent".

    Returns:
        AgentResult with success status, output, and turn count.
    """
    from workflow.dispatch_log import DispatchRecord, DispatchTimer, get_active_dispatch_log

    if adapter is None:
        adapter = get_adapter(model)

    # Log dispatch metadata
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)

    role_label = role.replace("_", " ").title()
    console.print(
        f"  Dispatching [bold]{role_label}[/bold]: model={model}, prompt_tokens=~{prompt_tokens}"
    )

    dispatch_log = get_active_dispatch_log()
    dispatch_record: DispatchRecord | None = None
    if dispatch_log is not None:
        dispatch_record = dispatch_log.start_dispatch(
            role=role,
            model=model,
            prompt=prompt,
            conversation_log=conversation_log,
            input_tokens=prompt_tokens,
        )
        conversation_log = dispatch_record.conversation_path

    args = adapter.build_args(
        model=model,
        json_schema=json_schema,
        mcp_servers=mcp_servers,
        streaming=conversation_log is not None,
    )

    # Clear CLAUDECODE env var to allow nested dispatch from within a Claude session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    timer = DispatchTimer()
    timer.start()

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
            timeout=timeout,
        )
    else:
        # Simple mode: subprocess.run (no conversation logging)
        result = _dispatch_simple(
            args=args,
            prompt=prompt,
            adapter=adapter,
            env=env,
            cwd=cwd,
            timeout=timeout,
        )

    duration_ms = timer.elapsed_ms

    # Record to unified dispatch log if active
    if dispatch_log is not None:
        dispatch_log.record(
            dispatch=dispatch_record,
            role=role,
            model=model,
            prompt=prompt,
            output=result.output or "",
            success=result.success,
            exit_code=result.exit_code,
            turns=result.turns,
            duration_ms=duration_ms,
        )

    status = "[green]success[/green]" if result.success else "[red]failed[/red]"
    turns = result.turns or "unknown"
    console.print(
        f"  {role_label} complete: {status}, turns={turns}, duration={duration_ms / 1000:.1f}s"
    )

    return result


def _dispatch_simple(
    args: list[str],
    prompt: str,
    adapter: AgentAdapter,
    env: dict,
    cwd: Path,
    timeout: int = 600,
) -> AgentResult:
    """Run agent via subprocess.run (no streaming, no conversation logging)."""
    effective_timeout = timeout if timeout > 0 else None
    try:
        completed = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Agent dispatch timed out after %ds", timeout)
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
    timeout: int = 0,
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

        timed_out = False
        deadline = time.monotonic() + timeout if timeout > 0 else None

        # Read stdout incrementally so transcript events are visible while the
        # dispatch runs. This preserves timeouts for long-running planner and
        # verifier calls that now use the streaming path.
        if process.stdout is not None:
            stdout_fd = process.stdout.fileno()
            while True:
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                    with contextlib.suppress(OSError):
                        process.kill()
                    break

                ready, _, _ = select.select([stdout_fd], [], [], 0.1)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        stdout_lines.append(line)
                        conv_logger.process_line(line)
                        continue
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        stdout_lines.append(remaining)
                        for line in remaining.splitlines(keepends=True):
                            conv_logger.process_line(line)
                    break

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

    if timed_out:
        logger.warning("Agent dispatch timed out after %ds", timeout)
        return AgentResult(
            success=False,
            output=stdout_output,
            exit_code=-1,
        )

    parsed_result = adapter.parse_result(completed)
    if (
        not parsed_result.success
        and adapter.name == "claude"
        and _is_structured_output_retry_failure(stdout_output)
    ):
        recovered = _recover_structured_output_from_conversation(conversation_log)
        if recovered is not None:
            logger.warning(
                "Recovered Claude structured output from conversation log after retry exhaustion"
            )
            return AgentResult(
                success=True,
                output=json.dumps(recovered),
                structured_output=recovered,
                exit_code=0,
                turns=parsed_result.turns,
            )

    return parsed_result


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


def get_dispatch_params(
    role: str,
    config: "EpicConfig | None",
) -> tuple[list[str] | None, int]:
    """Get MCP servers and timeout for a dispatch role from config.

    Resolves the ``[mcp]`` and ``[budgets]`` sections of the epic config
    into the parameters needed by ``dispatch_agent()``.

    Args:
        role: The dispatch role key (e.g. "planning", "gap_detection",
            "critique", "implementation").
        config: Epic configuration. If None, returns defaults.

    Returns:
        Tuple of (mcp_servers, timeout).
    """
    if config is None:
        return (None, 600)

    mcp_servers = config.mcp.get(role)
    budget = config.budgets.get(role)
    timeout = budget.timeout if budget else 600

    return (mcp_servers, timeout)
