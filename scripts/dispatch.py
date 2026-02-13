"""V2 agent dispatch module.

Dispatches prompts to Claude Code agents with the correct model, tools,
skills, MCP, and budget controls. ClaudeAdapter is the only concrete
implementation.

No dependency on run_epic.py or any V1 code.
"""

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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
}

# Fallback models per primary model (Section 8.6 Decision 6)
FALLBACK_MODELS: dict[str, str] = {
    "opus": "sonnet",
    "sonnet": "haiku",
    "haiku": "haiku",  # no cheaper fallback
}

# Tool restrictions per agent role (Section 8.2 Strategy 4)
TOOL_SETS: dict[str, list[str]] = {
    "planning": ["Read", "Bash", "Glob", "Grep"],
    "implementation": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "validation_browser": ["Read", "Bash", "Glob", "Grep"],
    "validation_api": ["Bash", "Read", "Glob", "Grep"],
    "regression": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
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
# ClaudeAdapter
# ---------------------------------------------------------------------------


class ClaudeAdapter:
    """Claude Code CLI adapter.

    Passes prompt via stdin (-p -) to avoid OS argument length limits.
    Model, tools, skills, and MCP are passed as individual CLI flags.
    """

    @property
    def name(self) -> str:
        return "claude"

    def build_args(
        self,
        _prompt: str,
        model: str,
        tools: list[str],
        _skills: list[str],
        mcp_config: dict | None,
        max_turns: int,
        max_budget_usd: float,
        json_schema: dict | None,
        fallback_model: str | None = None,
    ) -> list[str]:
        """Build CLI arguments. Prompt is piped via stdin by the caller.

        _prompt and _skills are accepted for protocol compatibility but
        not embedded in args. The caller pipes prompt via stdin.
        """
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

        if tools:
            args.extend(["--tools", ",".join(tools)])

        if mcp_config:
            mcp_json = json.dumps({"mcpServers": mcp_config})
            args.extend(["--strict-mcp-config", "--mcp-config", mcp_json])

        if json_schema:
            args.extend(["--json-schema", json.dumps(json_schema)])

        if fallback_model:
            args.extend(["--fallback-model", fallback_model])

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
# MCP configuration builder
# ---------------------------------------------------------------------------


def detect_chrome_executable() -> str | None:
    """Find Chrome/Chromium executable on the system."""
    for candidate in ["google-chrome", "chromium", "chromium-browser"]:
        result = subprocess.run(
            ["which", candidate],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def build_mcp_config(mcp_servers: list[str]) -> dict | None:
    """Build MCP server configuration from a list of required server names.

    Supported server names:
    - "chrome-devtools": Chrome DevTools MCP for browser inspection
    - "playwright": Playwright MCP for browser automation

    Args:
        mcp_servers: List of MCP server names required by the story.

    Returns:
        MCP config dict (without the outer "mcpServers" key), or None
        if no MCP servers are needed.
    """
    if not mcp_servers:
        return None

    config: dict = {}

    if "chrome-devtools" in mcp_servers:
        chrome_exe = detect_chrome_executable()
        chrome_args = ["-y", "chrome-devtools-mcp@latest"]
        if chrome_exe:
            chrome_args.extend(["--executablePath", chrome_exe])
        chrome_args.append("--headless")

        config["chrome-devtools"] = {
            "command": "npx",
            "args": chrome_args,
        }

    if "playwright" in mcp_servers:
        config["playwright"] = {
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest"],
        }

    return config if config else None


# ---------------------------------------------------------------------------
# Pre-flight MCP check
# ---------------------------------------------------------------------------


class MCPUnavailableError(Exception):
    """Raised when a required MCP server is unavailable."""

    def __init__(self, server_name: str, reason: str) -> None:
        self.server_name = server_name
        self.reason = reason
        super().__init__(f"MCP server '{server_name}' unavailable: {reason}")


def preflight_mcp_check(mcp_servers: list[str]) -> None:
    """Verify that required MCP servers are available before dispatch.

    Checks that npx is available (required for both chrome-devtools and
    playwright MCP servers). For chrome-devtools, also checks that a
    Chrome/Chromium executable can be found.

    Args:
        mcp_servers: List of required MCP server names.

    Raises:
        MCPUnavailableError: If a required MCP server cannot be started.
    """
    if not mcp_servers:
        return

    # Check npx availability (common requirement)
    npx_check = subprocess.run(
        ["which", "npx"],
        capture_output=True,
        text=True,
    )
    if npx_check.returncode != 0:
        server = mcp_servers[0]
        raise MCPUnavailableError(server, "npx not found — required for MCP servers")

    if "chrome-devtools" in mcp_servers:
        chrome_exe = detect_chrome_executable()
        if chrome_exe is None:
            raise MCPUnavailableError(
                "chrome-devtools",
                "No Chrome/Chromium executable found. "
                "Install google-chrome, chromium, or chromium-browser.",
            )


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

# Module-level adapter instance (V2 is Claude-only)
_claude_adapter = ClaudeAdapter()


def dispatch_agent(
    prompt: str,
    model: str,
    tools: list[str],
    skills: list[str] | None = None,
    mcp_config: dict | None = None,
    max_turns: int = 30,
    max_budget_usd: float = 3.0,
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
    fallback_model: str | None = None,
    adapter: ClaudeAdapter | None = None,
) -> AgentResult:
    """Dispatch a prompt to an agent and return the structured result.

    Constructs CLI arguments via the adapter, runs the subprocess,
    and parses the result into an AgentResult. Logs dispatch metadata
    (model, prompt_hash, prompt_tokens, skill_tokens).

    Args:
        prompt: The full agent prompt text.
        model: Model identifier (e.g. "opus", "sonnet", "haiku").
        tools: List of tool names the agent may use.
        skills: List of skill names to inject (optional).
        mcp_config: MCP server config dict (optional).
        max_turns: Maximum conversation turns.
        max_budget_usd: Dollar cap for this invocation.
        json_schema: JSON schema for structured output (optional).
        cwd: Working directory for the subprocess.
        fallback_model: Model to fall back to on HTTP 529 overload.
        adapter: Provider adapter to use (defaults to ClaudeAdapter).

    Returns:
        AgentResult with success status, output, cost, and turn count.
    """
    if adapter is None:
        adapter = _claude_adapter

    if skills is None:
        skills = []

    # Resolve fallback model from defaults if not provided
    if fallback_model is None:
        fallback_model = FALLBACK_MODELS.get(model)

    # Log dispatch metadata
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)

    logger.info(
        "Dispatching agent: model=%s, tools=%s, skills=%s, max_turns=%d, "
        "max_budget=$%.2f, json_schema=%s, prompt_hash=%s, prompt_tokens=%d",
        model,
        tools,
        skills,
        max_turns,
        max_budget_usd,
        bool(json_schema),
        prompt_hash,
        prompt_tokens,
    )

    # Write prompt to logs dir for post-mortem debugging
    _log_dispatch_prompt(prompt, prompt_hash, model)

    # Build CLI arguments — prompt and skills passed positionally because
    # ClaudeAdapter names them _prompt/_skills (unused, piped via stdin).
    args = adapter.build_args(
        prompt,
        model,
        tools,
        skills,
        mcp_config=mcp_config,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        fallback_model=fallback_model,
    )

    # Run subprocess — prompt piped via stdin to avoid OS arg length limits.
    # Clear CLAUDECODE env var to allow nested dispatch from within a Claude session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
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

    # Parse result
    result = adapter.parse_result(completed)

    logger.info(
        "Agent complete: success=%s, exit_code=%d, cost=$%s, turns=%s",
        result.success,
        result.exit_code,
        result.cost_usd or "unknown",
        result.turns or "unknown",
    )

    return result


def dispatch_with_fallback(
    prompt: str,
    primary_model: str,
    fallback_model: str,
    tools: list[str],
    skills: list[str] | None = None,
    mcp_config: dict | None = None,
    max_turns: int = 30,
    max_budget_usd: float = 3.0,
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
    adapter: ClaudeAdapter | None = None,
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
        skills: Skill names to inject.
        mcp_config: MCP server config.
        max_turns: Maximum turns.
        max_budget_usd: Dollar cap.
        json_schema: Structured output schema.
        cwd: Working directory.
        adapter: Provider adapter.

    Returns:
        AgentResult from either the primary or fallback dispatch.
    """
    # Primary dispatch
    result = dispatch_agent(
        prompt=prompt,
        model=primary_model,
        tools=tools,
        skills=skills,
        mcp_config=mcp_config,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        cwd=cwd,
        fallback_model=fallback_model,
        adapter=adapter,
    )

    if result.success:
        return result

    # Check if failure is transient
    if not result.is_overload_or_transient:
        return result  # Real failure — don't retry

    logger.warning(
        "Primary dispatch failed with transient error (model=%s). "
        "Retrying with fallback model=%s",
        primary_model,
        fallback_model,
    )

    # Fallback dispatch — no further fallback model
    fallback_result = dispatch_agent(
        prompt=prompt,
        model=fallback_model,
        tools=tools,
        skills=skills,
        mcp_config=mcp_config,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=json_schema,
        cwd=cwd,
        fallback_model=None,  # No further fallback
        adapter=adapter,
    )

    return fallback_result


# ---------------------------------------------------------------------------
# Convenience helpers for dispatch metadata
# ---------------------------------------------------------------------------


def get_dispatch_metadata(
    prompt: str,
    model: str,
    skills: list[str] | None = None,
) -> dict:
    """Build metadata dict suitable for JSONL agent_dispatched events.

    Args:
        prompt: The prompt text.
        model: Model identifier.
        skills: List of skill names.

    Returns:
        Dict with model, prompt_hash, prompt_tokens, skill_tokens.
    """
    return {
        "model": model,
        "prompt_hash": compute_prompt_hash(prompt),
        "prompt_tokens": estimate_tokens(prompt),
        "skill_tokens": 0,  # Skills loaded from project config, not counted separately
    }


def get_budget_defaults(agent_type: str) -> dict[str, int | float]:
    """Get default max_turns and max_budget_usd for an agent type.

    Args:
        agent_type: One of "planning", "architecture", "implementation",
            "validation", "regression".

    Returns:
        Dict with "max_turns" (int) and "max_budget_usd" (float).
    """
    return dict(BUDGET_DEFAULTS.get(agent_type, BUDGET_DEFAULTS["implementation"]))


def get_tools_for_role(role: str) -> list[str]:
    """Get the tool restriction list for an agent role.

    Args:
        role: One of "implementation", "validation_browser",
            "validation_api", "regression".

    Returns:
        List of tool name strings.
    """
    return list(TOOL_SETS.get(role, TOOL_SETS["implementation"]))
