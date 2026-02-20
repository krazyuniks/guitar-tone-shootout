# Epic Workflow Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the full epic workflow pipeline as described in `wiki/Epic-Workflow.md` — filling the gaps between the current codebase and the canonical spec.

**Architecture:** The pipeline is a stateless Python CLI orchestrator that dispatches AI agents via subprocess. It uses JSONL for crash recovery, per-epic config profiles for model assignment, and per-dispatch MCP config + conversation logging for full agent traceability. All interactive stages (brainstorming, gap detection) run as CC sessions; the execution pipeline runs as a terminal process.

**Tech Stack:** Python 3.11+, Typer CLI, Pydantic v2, TOML config, JSONL logging, subprocess.Popen for streaming agent output.

---

## Gap Analysis

| Gap | Spec Section | Current State | Phase |
|-----|-------------|---------------|-------|
| Epic config profiles | Model Assignment, Stage 4 Config | Models hardcoded throughout | 1 |
| Per-dispatch MCP config | Agent Dispatch | `no_mcp` flag only, no per-role control | 2 |
| Conversation logging | Conversation Logging | `subprocess.run` + `--output-format json` | 2 |
| Epic ingest structural validation | Stage 1 | No section validation | 3 |
| Stage 2b gap detection | Stage 2b | Entirely missing | 4 |
| Config validation | Stage 4 Config Validation | Entirely missing | 5 |
| Stage 0 brainstorming | Stage 0 | Entirely missing | 6 |

---

## Phase 1: Epic Config Profiles

**Goal:** Replace hardcoded model references with per-epic TOML config files. Every dispatch reads its model/budget/MCP from config, not constants.

**Why first:** Everything downstream (MCP config, gap detection, config validation) reads from the epic config. Without this, model assignment is scattered across a dozen hardcoded strings.

**Files:**
- Create: `workflow/epic_config.py`
- Create: `workflow/default_config.toml`
- Modify: `workflow/orchestrator.py`
- Modify: `workflow/story_executor.py`
- Modify: `workflow/cli.py`
- Test: `tests/unit/workflow/test_epic_config.py`

### Task 1.1: Create the config model and loader

**Files:**
- Create: `workflow/epic_config.py`
- Create: `workflow/default_config.toml`

**Step 1: Write the failing test**

Create `tests/unit/workflow/` directory and test file:

```python
# tests/unit/workflow/test_epic_config.py
"""Tests for epic configuration loading and validation."""

import tomllib
from pathlib import Path

import pytest

from workflow.epic_config import EpicConfig, load_config, DEFAULT_CONFIG_PATH


class TestEpicConfigParsing:
    """Test TOML parsing into EpicConfig model."""

    def test_load_default_config(self):
        """Default config file parses without errors."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.models.planner is not None
        assert config.models.implementor is not None
        assert config.models.plan_critic is not None
        assert config.models.story_critic is not None
        assert config.models.epic_critic is not None

    def test_cross_model_constraint_planner(self):
        """Plan critic must differ from planner."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.models.plan_critic != config.models.planner

    def test_cross_model_constraint_implementor(self):
        """Story critic and epic critic must differ from implementor."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.models.story_critic != config.models.implementor
        assert config.models.epic_critic != config.models.implementor

    def test_budget_defaults_present(self):
        """Each role has budget defaults."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.budgets.implementation.max_turns > 0
        assert config.budgets.implementation.max_budget_usd > 0
        assert config.budgets.planning.max_turns > 0

    def test_mcp_roles_present(self):
        """MCP config has entries for key roles."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert "implementation" in config.mcp
        assert "critique" in config.mcp

    def test_load_epic_override(self, tmp_path):
        """Epic-level config overrides defaults."""
        override = tmp_path / "config.toml"
        override.write_text(
            '[models]\nimplementor = "haiku"\n',
            encoding="utf-8",
        )
        config = load_config(DEFAULT_CONFIG_PATH, override)
        assert config.models.implementor == "haiku"
        # Non-overridden fields retain defaults
        assert config.models.planner is not None

    def test_invalid_cross_model_raises(self, tmp_path):
        """Config where critic == implementor raises ValueError."""
        override = tmp_path / "config.toml"
        override.write_text(
            '[models]\nimplementor = "opus"\nstory_critic = "opus"\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must be different"):
            load_config(DEFAULT_CONFIG_PATH, override)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/workflow/test_epic_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'workflow.epic_config'`

**Step 3: Write `workflow/default_config.toml`**

```toml
# Default epic configuration profile.
# Copied to .planning/epics/E{N}/config.toml per epic.
# User selects options interactively during Stage 4 setup.

[models]
# Planner and plan critic (Stage 3)
planner = "opus"
plan_critic = "codex"

# Story implementor and critics (Stage 4)
# Constraint: story_critic != implementor, epic_critic != implementor
implementor = "codex"
story_critic = "opus"
epic_critic = "opus"

[budgets.planning]
max_turns = 50
max_budget_usd = 5.00

[budgets.implementation]
max_turns = 40
max_budget_usd = 4.00

[budgets.validation]
max_turns = 15
max_budget_usd = 0.50

[budgets.critique_plan]
max_turns = 20
max_budget_usd = 5.00

[budgets.critique_story]
max_turns = 15
max_budget_usd = 3.00

[budgets.critique_epic]
max_turns = 20
max_budget_usd = 8.00

[budgets.gap_detection]
max_turns = 30
max_budget_usd = 3.00

# MCP servers per dispatch role.
# Empty list = --strict-mcp-config --mcp-config '{"mcpServers":{}}'
# Named servers are resolved from ~/.claude/settings.json + ~/.claude.json
[mcp]
implementation = []
critique = []
validation = []
gap_detection = []
```

**Step 4: Write `workflow/epic_config.py`**

```python
"""Epic configuration profile — per-epic TOML-based model/budget/MCP assignment.

Each epic gets a config.toml (copied from workflow/default_config.toml on first
run, user-editable). The config defines which models handle each role, budget
limits per role, and MCP server assignments per dispatch type.

The only hard constraint: critique models must differ from implementation models
(cross-model verification principle).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "default_config.toml"


@dataclass(frozen=True)
class ModelConfig:
    """Model assignments per role."""
    planner: str = "opus"
    plan_critic: str = "codex"
    implementor: str = "codex"
    story_critic: str = "opus"
    epic_critic: str = "opus"


@dataclass(frozen=True)
class BudgetConfig:
    """Budget limits for a single role."""
    max_turns: int = 30
    max_budget_usd: float = 3.0


@dataclass(frozen=True)
class EpicConfig:
    """Complete epic configuration profile."""
    models: ModelConfig = field(default_factory=ModelConfig)
    budgets: dict[str, BudgetConfig] = field(default_factory=dict)
    mcp: dict[str, list[str]] = field(default_factory=dict)


def _parse_toml(path: Path) -> dict:
    """Read and parse a TOML file."""
    with path.open("rb") as f:
        return tomllib.load(f)


def _merge_dicts(base: dict, override: dict) -> dict:
    """Deep-merge override into base (override wins)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _validate_cross_model(models: ModelConfig) -> None:
    """Enforce: critic models must be different from their target models."""
    if models.plan_critic == models.planner:
        raise ValueError(
            f"plan_critic ({models.plan_critic}) must be different from "
            f"planner ({models.planner})"
        )
    if models.story_critic == models.implementor:
        raise ValueError(
            f"story_critic ({models.story_critic}) must be different from "
            f"implementor ({models.implementor})"
        )
    if models.epic_critic == models.implementor:
        raise ValueError(
            f"epic_critic ({models.epic_critic}) must be different from "
            f"implementor ({models.implementor})"
        )


def load_config(
    default_path: Path = DEFAULT_CONFIG_PATH,
    override_path: Path | None = None,
) -> EpicConfig:
    """Load epic config from default + optional per-epic override.

    Args:
        default_path: Path to the default config TOML.
        override_path: Optional per-epic override TOML (merged on top).

    Returns:
        Validated EpicConfig.

    Raises:
        ValueError: If cross-model constraints are violated.
        FileNotFoundError: If default_path doesn't exist.
    """
    data = _parse_toml(default_path)

    if override_path is not None and override_path.is_file():
        override_data = _parse_toml(override_path)
        data = _merge_dicts(data, override_data)

    # Parse models
    models_data = data.get("models", {})
    models = ModelConfig(**{k: v for k, v in models_data.items() if k in ModelConfig.__dataclass_fields__})
    _validate_cross_model(models)

    # Parse budgets
    budgets_data = data.get("budgets", {})
    budgets = {}
    for role, budget_dict in budgets_data.items():
        if isinstance(budget_dict, dict):
            budgets[role] = BudgetConfig(**budget_dict)

    # Parse MCP
    mcp = data.get("mcp", {})

    return EpicConfig(models=models, budgets=budgets, mcp=mcp)


def ensure_epic_config(epic_dir: Path) -> Path:
    """Ensure config.toml exists in the epic directory.

    If it doesn't exist, copies the default. Returns the path to the
    epic's config.toml.
    """
    config_path = epic_dir / "config.toml"
    if not config_path.is_file():
        import shutil
        epic_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEFAULT_CONFIG_PATH, config_path)
    return config_path
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/unit/workflow/test_epic_config.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add workflow/epic_config.py workflow/default_config.toml tests/unit/workflow/test_epic_config.py tests/unit/workflow/__init__.py
git commit -m "feat(workflow): add epic config profiles with TOML loader"
```

### Task 1.2: Wire config into orchestrator and story executor

**Files:**
- Modify: `workflow/orchestrator.py` (load config, pass to execute_story)
- Modify: `workflow/story_executor.py` (read model/budget from config instead of story dict)
- Modify: `workflow/cli.py` (ensure config exists during planning)

**Step 1: Modify `workflow/orchestrator.py`**

In `run_epic()`, after loading the plan, load the epic config:

```python
# After: plan = _load_plan(epic_dir)
from workflow.epic_config import EpicConfig, ensure_epic_config, load_config

config_path = ensure_epic_config(epic_dir)
config = load_config(override_path=config_path)
```

Pass `config` to `execute_story()`:

```python
success = execute_story(
    story=next_story,
    plan=plan,
    epic_dir=epic_dir,
    event_logger=story_logger,
    completed_stories=completed_stories,
    config=config,  # NEW
)
```

In `_run_epic_critique()`, use `config.models.epic_critic` instead of hardcoded `"opus"`:

```python
def _run_epic_critique(
    plan: dict,
    epic_dir: Path,
    events: list[dict],
    epic_logger: EventLogger,
    config: EpicConfig,  # NEW parameter
) -> tuple[bool, list, float | None]:
```

Replace `model="opus"` with `model=config.models.epic_critic`.

**Step 2: Modify `workflow/story_executor.py`**

Add `config: EpicConfig` parameter to `execute_story()` and `_dispatch_and_validate_loop()`. Replace hardcoded model reads from `story["agent"]["model"]` with `config.models.implementor`. Replace hardcoded `"opus"` in `_run_story_critique()` with `config.models.story_critic`.

Key change in `_dispatch_and_validate_loop`:

```python
# Before:
model = agent.get("model", "sonnet")

# After:
from workflow.epic_config import EpicConfig
model = config.models.implementor
```

And in `_run_story_critique`:

```python
# Before:
result = dispatch_agent(prompt=prompt, model="opus", ...)

# After:
result = dispatch_agent(prompt=prompt, model=config.models.story_critic, ...)
```

**Step 3: Modify `workflow/cli.py`**

In `_run_planning_pipeline()`, ensure the epic config exists and use configured planner/critic models:

```python
from workflow.epic_config import ensure_epic_config, load_config

config_path = ensure_epic_config(epic_dir)
config = load_config(override_path=config_path)
```

**Step 4: Run existing tests**

Run: `just check`
Expected: All checks pass (no existing workflow tests to break, just lint/types)

**Step 5: Commit**

```bash
git add workflow/orchestrator.py workflow/story_executor.py workflow/cli.py
git commit -m "feat(workflow): wire epic config into orchestrator and story executor"
```

---

## Phase 2: Dispatch Refactor (MCP Config + Conversation Logging)

**Goal:** Refactor dispatch.py to (a) support per-dispatch MCP server control via `--strict-mcp-config --mcp-config <json>`, and (b) use `subprocess.Popen` with `--output-format stream-json` for line-by-line conversation capture to per-dispatch JSONL files.

**Why together:** Both changes modify the adapter interface and the core `dispatch_agent()` function. Doing them separately would require two adapter interface migrations.

**Files:**
- Create: `workflow/conversation_logger.py`
- Modify: `workflow/dispatch.py`
- Modify: `workflow/story_executor.py` (pass conversation log path, add to JSONL events)
- Test: `tests/unit/workflow/test_conversation_logger.py`

### Task 2.1: Create conversation logger

**Files:**
- Create: `workflow/conversation_logger.py`
- Test: `tests/unit/workflow/test_conversation_logger.py`

**Step 1: Write the failing test**

```python
# tests/unit/workflow/test_conversation_logger.py
"""Tests for conversation JSONL envelope logging."""

import json
from pathlib import Path

from workflow.conversation_logger import ConversationLogger


class TestConversationLogger:
    """Test the passthrough envelope conversation logger."""

    def test_write_envelope(self, tmp_path):
        """Each line wraps the payload in an envelope."""
        log_path = tmp_path / "conversation.jsonl"
        logger = ConversationLogger(log_path, provider="claude", model="opus")

        payload = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}
        logger.write_event(payload)

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        envelope = json.loads(lines[0])
        assert envelope["provider"] == "claude"
        assert envelope["model"] == "opus"
        assert envelope["seq"] == 1
        assert envelope["payload"] == payload
        assert "ts" in envelope

    def test_sequence_numbers_increment(self, tmp_path):
        """Sequence numbers are monotonically increasing."""
        log_path = tmp_path / "conversation.jsonl"
        logger = ConversationLogger(log_path, provider="claude", model="sonnet")

        for i in range(3):
            logger.write_event({"type": "test", "n": i})

        lines = log_path.read_text().strip().split("\n")
        seqs = [json.loads(line)["seq"] for line in lines]
        assert seqs == [1, 2, 3]

    def test_non_json_line_skipped(self, tmp_path):
        """Non-JSON lines from stream are silently skipped."""
        log_path = tmp_path / "conversation.jsonl"
        logger = ConversationLogger(log_path, provider="claude", model="opus")

        logger.process_line("not json at all")
        logger.process_line('{"type": "result", "data": 1}')

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1  # Only the valid JSON line
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/workflow/test_conversation_logger.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `workflow/conversation_logger.py`**

```python
"""Conversation JSONL logger — passthrough envelope for agent transcripts.

Each agent dispatch produces a separate conversation log file. Every line
from the agent's --output-format stream-json stdout is wrapped in a thin
envelope and appended to the file:

    {"ts": "ISO 8601", "provider": "claude", "model": "opus", "seq": 1, "payload": {<native event>}}

The payload is written as-is (passthrough, not normalised). This is lossless.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class ConversationLogger:
    """Append-only conversation JSONL logger with passthrough envelope.

    Args:
        log_path: Path to the conversation JSONL file.
        provider: Provider name ("claude" or "codex").
        model: Model identifier (e.g. "opus", "sonnet").
    """

    def __init__(self, log_path: Path, provider: str, model: str) -> None:
        self.log_path = log_path
        self.provider = provider
        self.model = model
        self._seq = 0

        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write_event(self, payload: dict) -> None:
        """Write a single envelope-wrapped event to the log."""
        self._seq += 1
        envelope = {
            "ts": datetime.now(UTC).isoformat(),
            "provider": self.provider,
            "model": self.model,
            "seq": self._seq,
            "payload": payload,
        }
        line = json.dumps(envelope, default=str)
        with self.log_path.open("a") as f:
            f.write(line + "\n")
            f.flush()

    def process_line(self, raw_line: str) -> None:
        """Process a single line from stream-json stdout.

        Parses the line as JSON. If it's valid JSON, wraps it in an
        envelope and writes it. Non-JSON lines are silently skipped
        (stream-json may emit non-JSON lines during init).
        """
        raw_line = raw_line.strip()
        if not raw_line:
            return
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            return
        self.write_event(payload)
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/workflow/test_conversation_logger.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add workflow/conversation_logger.py tests/unit/workflow/test_conversation_logger.py
git commit -m "feat(workflow): add conversation JSONL logger with passthrough envelope"
```

### Task 2.2: Refactor dispatch.py — Popen + stream-json + MCP config

**Files:**
- Modify: `workflow/dispatch.py`

This is the largest single task. The key changes:

1. **AgentAdapter protocol** — add `mcp_config` parameter to `build_args()`
2. **ClaudeAdapter.build_args()** — switch from `--output-format json` to `--output-format stream-json`, always pass `--strict-mcp-config --mcp-config <json>`
3. **dispatch_agent()** — accept `mcp_servers: list[str]`, `conversation_log_path: Path | None` parameters. Use `subprocess.Popen` instead of `subprocess.run`. Read stdout line-by-line, feeding each line to a ConversationLogger. Collect the final result event for the AgentResult.
4. **ClaudeAdapter.parse_result()** — adapt to work with collected stream events instead of single JSON blob
5. **MCP config builder** — resolve named servers from `~/.claude/settings.json` + `~/.claude.json` (same pattern as `cld` script)

**Step 1: Add MCP config resolution**

Add to `dispatch.py`:

```python
def build_mcp_config_json(server_names: list[str]) -> str:
    """Build --mcp-config JSON from a list of server names.

    Reads MCP server configs from:
    1. ~/.claude/settings.json
    2. ~/.claude/settings.local.json
    3. ~/.claude.json

    If server_names is empty, returns '{"mcpServers":{}}' (no servers).

    Args:
        server_names: List of MCP server names to enable.

    Returns:
        JSON string for --mcp-config.

    Raises:
        ValueError: If a named server is not found in any settings file.
    """
```

This function merges MCP server configs from settings files (same algorithm as `cld` script) and builds the JSON.

**Step 2: Modify ClaudeAdapter.build_args()**

```python
def build_args(
    self,
    model: str,
    tools: list[str],
    max_turns: int,
    max_budget_usd: float,
    json_schema: dict | None,
    fallback_model: str | None = None,
    mcp_config_json: str | None = None,  # CHANGED from no_mcp: bool
) -> list[str]:
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
        "stream-json",  # CHANGED from "json"
        "--dangerously-skip-permissions",
    ]

    args.extend(["--tools", ",".join(tools)])

    if json_schema:
        args.extend(["--json-schema", json.dumps(json_schema)])

    if fallback_model and fallback_model != model:
        args.extend(["--fallback-model", fallback_model])

    # Always use strict MCP config — explicit control over which servers load
    mcp_json = mcp_config_json or '{"mcpServers":{}}'
    args.extend(["--strict-mcp-config", "--mcp-config", mcp_json])

    return args
```

**Step 3: Refactor dispatch_agent() to use Popen**

```python
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
    mcp_servers: list[str] | None = None,
    conversation_log_path: Path | None = None,
) -> AgentResult:
```

The implementation:
1. Build MCP config JSON from `mcp_servers` list
2. Build CLI args via adapter (passing `mcp_config_json`)
3. Open `subprocess.Popen` with `stdout=PIPE, stderr=PIPE`
4. Write prompt to stdin, close stdin
5. Read stdout line-by-line:
   - Feed each line to `ConversationLogger.process_line()` if `conversation_log_path` is set
   - Collect stream events to find the final `result` event
6. Wait for process to complete
7. Build `AgentResult` from the collected result event

**Key implementation detail** — the result event extraction:

```python
from workflow.conversation_logger import ConversationLogger

# ... in dispatch_agent():

conv_logger = None
if conversation_log_path:
    provider = adapter.name
    conv_logger = ConversationLogger(conversation_log_path, provider=provider, model=model)

env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
process = subprocess.Popen(
    args,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=cwd,
    env=env,
)

# Write prompt and close stdin
process.stdin.write(prompt)
process.stdin.close()

# Read stdout line by line
result_event = None
for line in process.stdout:
    line = line.rstrip("\n")
    if not line:
        continue

    # Log to conversation file
    if conv_logger:
        conv_logger.process_line(line)

    # Parse to find the result event
    try:
        event = json.loads(line)
        if isinstance(event, dict) and event.get("type") == "result":
            result_event = event
    except json.JSONDecodeError:
        pass

stderr_output = process.stderr.read()
process.wait()

# Build AgentResult from result_event
exit_code = process.returncode
# ... parse result_event for output, cost, turns
```

**Step 4: Update AgentAdapter protocol**

Replace `no_mcp: bool` with `mcp_config_json: str | None` in the protocol and both adapters.

**Step 5: Update all callers**

Every call to `dispatch_agent()` and `dispatch_with_fallback()` must:
- Replace `no_mcp=True` with `mcp_servers=[]`
- Add `conversation_log_path=...` where appropriate (story executor, plan verifier, etc.)

**Step 6: Run checks**

Run: `just check`
Expected: PASS (lint, types)

**Step 7: Commit**

```bash
git add workflow/dispatch.py
git commit -m "feat(workflow): refactor dispatch to Popen + stream-json + per-dispatch MCP config"
```

### Task 2.3: Wire conversation logging into story executor

**Files:**
- Modify: `workflow/story_executor.py`

In `_dispatch_and_validate_loop()`, compute the conversation log path before dispatch:

```python
conversation_log_path = epic_dir / "stories" / story_id / f"conversation-attempt-{attempt}.jsonl"
```

Pass it to `dispatch_with_fallback()`.

In the `agent_dispatched` JSONL event, add the `conversation_log` field:

```python
event_logger.log_event(
    "agent_dispatched",
    story_id=story_id,
    attempt=attempt,
    conversation_log=str(conversation_log_path.relative_to(epic_dir)),  # NEW
    **metadata,
)
```

Do the same for critique dispatches in `_run_story_critique()` and the epic critique in `orchestrator.py`.

**Step 1: Commit**

```bash
git add workflow/story_executor.py workflow/orchestrator.py
git commit -m "feat(workflow): wire conversation logging into story and critique dispatches"
```

---

## Phase 3: Epic Ingest Structural Validation

**Goal:** Stage 1 ingest validates that the GitHub issue has the enriched epic format before writing EPIC.md.

**Spec reference:** "Structural validation: verifies the enriched epic format — the expected sections (Summary, Observable Outcomes, Decisions, Regression Boundaries) must be present."

**Files:**
- Modify: `workflow/epic_ingest.py`
- Test: `tests/unit/workflow/test_epic_ingest.py`

### Task 3.1: Add structural validation to epic ingest

**Step 1: Write the failing test**

```python
# tests/unit/workflow/test_epic_ingest.py
"""Tests for epic ingest structural validation."""

import pytest

from workflow.epic_ingest import IngestionError, _validate_enriched_epic


class TestEnrichedEpicValidation:
    """Test that enriched epic body has required sections."""

    def test_valid_enriched_epic(self):
        """Body with all 4 required sections passes."""
        body = (
            "## Summary\nOne paragraph.\n\n"
            "## Observable Outcomes\n- [ ] Outcome 1\n\n"
            "## Decisions\n- Approach: X\n\n"
            "## Regression Boundaries\n- Existing behaviour\n"
        )
        _validate_enriched_epic(body)  # Should not raise

    def test_missing_summary_raises(self):
        """Missing Summary section raises IngestionError."""
        body = (
            "## Observable Outcomes\n- [ ] Outcome 1\n\n"
            "## Decisions\n- Approach: X\n\n"
            "## Regression Boundaries\n- Existing behaviour\n"
        )
        with pytest.raises(IngestionError, match="Summary"):
            _validate_enriched_epic(body)

    def test_missing_observable_outcomes_raises(self):
        """Missing Observable Outcomes section raises IngestionError."""
        body = (
            "## Summary\nOne paragraph.\n\n"
            "## Decisions\n- Approach: X\n\n"
            "## Regression Boundaries\n- Existing behaviour\n"
        )
        with pytest.raises(IngestionError, match="Observable Outcomes"):
            _validate_enriched_epic(body)

    def test_case_insensitive_match(self):
        """Section headings match case-insensitively."""
        body = (
            "## summary\nOne paragraph.\n\n"
            "## observable outcomes\n- [ ] Outcome 1\n\n"
            "## decisions\n- Approach: X\n\n"
            "## regression boundaries\n- Existing behaviour\n"
        )
        _validate_enriched_epic(body)  # Should not raise
```

**Step 2: Write the implementation**

Add to `workflow/epic_ingest.py`:

```python
REQUIRED_SECTIONS = [
    "Summary",
    "Observable Outcomes",
    "Decisions",
    "Regression Boundaries",
]


def _validate_enriched_epic(body: str) -> None:
    """Validate that the epic body contains required enriched sections.

    Raises:
        IngestionError: If any required section is missing.
    """
    body_lower = body.lower()
    missing = []
    for section in REQUIRED_SECTIONS:
        # Match ## Section Name (case-insensitive)
        if f"## {section.lower()}" not in body_lower:
            missing.append(section)

    if missing:
        raise IngestionError(
            f"Enriched epic missing required section(s): {', '.join(missing)}. "
            f"Run /epic brainstorm N to enrich the issue before ingestion."
        )
```

Call it in `ingest_epic()` after fetching the issue body:

```python
body = data.get("body", "")
_validate_enriched_epic(body)
```

**Step 3: Run tests**

Run: `python -m pytest tests/unit/workflow/test_epic_ingest.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add workflow/epic_ingest.py tests/unit/workflow/test_epic_ingest.py
git commit -m "feat(workflow): add structural validation for enriched epic format"
```

---

## Phase 4: Stage 2b Gap Detection

**Goal:** Implement the interactive gap detection stage between context assembly and planning. Agent identifies implementation gaps, critique agent reviews, interactive Q&A with the user, outputs `user-decisions.json`.

**Files:**
- Create: `workflow/gap_detection.py`
- Create: `workflow/references/gap-detection-guide.md` (copy from `.claude/skills/epic/references/question-bank.md`)
- Modify: `workflow/cli.py` (insert gap detection step between context assembly and planning)
- Modify: `workflow/plan_generator.py` (read user-decisions.json into planner prompt)

### Task 4.1: Create gap detection module

**Files:**
- Create: `workflow/gap_detection.py`

This module implements the Stage 2b gap detection process:

1. Build a prompt from EPIC.md + CONTEXT.md + gap-detection-guide.md
2. Dispatch gap detection agent (configured model) to identify gaps and derive questions
3. Dispatch critique agent (different model) to review the gaps
4. Print both exchanges on screen for user visibility
5. Present questions one at a time via terminal (typer)
6. Agent validates answers, may loop back for more questions
7. Agent confirms sufficiency
8. User accepts → write `user-decisions.json`

**Key data structures:**

```python
@dataclass
class GapQuestion:
    """A single gap-derived question for the user."""
    id: str
    gap_type: str  # ambiguity, assumption, contradiction, missing, bc_ownership, cross_bc
    question: str
    options: list[str]  # Multiple choice options (last is always "Other")
    recommendation: str | None  # Recommended option, if any

@dataclass
class GapAnswer:
    """User's answer to a gap question."""
    question_id: str
    answer: str
    rationale: str  # Why the user chose this
```

**Output format** (`user-decisions.json`):

```json
{
    "schema_v": 1,
    "epic_number": 95,
    "generated": "2026-02-20T12:00:00Z",
    "gaps_identified": 5,
    "gaps_after_critique": 7,
    "questions": [
        {
            "id": "Q1",
            "gap_type": "bc_ownership",
            "question": "Which BC owns the tag entity?",
            "options": ["core", "webapp"],
            "recommendation": "core",
            "answer": "core",
            "rationale": "Tags are domain-level, not presentation"
        }
    ],
    "decisions_summary": "..."
}
```

The module is interactive — it uses `typer.prompt()` and `typer.confirm()` for Q&A. The AI dispatch is via `dispatch_agent()` with the configured gap_detection model.

**Implementation notes:**

- The gap detection agent prompt includes the gap-detection-guide.md reference
- The critique agent is dispatched separately with `no_tools=True` (read-only analysis)
- Questions are presented one at a time with numbered options
- The agent's gap report and critique exchange are printed on screen (not hidden)
- A `run_gap_detection(epic_dir, config) -> Path` function is the public API

**Step 1: Write the module**

The module structure:

```python
"""Stage 2b: Gap detection — AI-identified gaps resolved through interactive Q&A.

Identifies implementation gaps between the epic requirements and the current
architecture/codebase, then resolves them through cross-model critique and
interactive conversation with the user.

Output: .planning/epics/E{N}/user-decisions.json
"""

import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import typer

from workflow.dispatch import dispatch_agent, dispatch_with_fallback
from workflow.epic_config import EpicConfig
from workflow.jsonl_logger import EventLogger

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_gap_detection(
    epic_dir: Path,
    config: EpicConfig,
    epic_logger: EventLogger,
) -> Path:
    """Run Stage 2b gap detection interactively.

    Args:
        epic_dir: Path to the epic directory.
        config: Epic configuration profile.
        epic_logger: JSONL event logger.

    Returns:
        Path to the written user-decisions.json.
    """
    # 1. Read inputs
    # 2. Build gap detection prompt
    # 3. Dispatch gap detection agent
    # 4. Dispatch critique agent on the gaps
    # 5. Present refined questions interactively
    # 6. Validate answers, loop if needed
    # 7. Confirm sufficiency
    # 8. Write user-decisions.json
    ...
```

Full implementation will follow the spec's 8-step process. Each step is a function within the module.

**Step 2: Commit**

```bash
git add workflow/gap_detection.py workflow/references/gap-detection-guide.md
git commit -m "feat(workflow): add Stage 2b gap detection module"
```

### Task 4.2: Integrate gap detection into CLI pipeline

**Files:**
- Modify: `workflow/cli.py`

Insert gap detection between Step 2 (Context Assembly) and Step 3 (Plan Generation):

```python
# Step 2b: Gap Detection
decisions_path = epic_dir / "user-decisions.json"
if _should_skip(decisions_path, "user-decisions.json"):
    console.print("[dim]Step 2b: Gap Detection — skipped[/dim]")
else:
    console.print("[bold]Step 2b:[/bold] Running gap detection...")
    from workflow.gap_detection import run_gap_detection

    try:
        path = run_gap_detection(epic_dir, config, epic_logger)
        console.print(f"  [green]Written:[/green] {path.relative_to(PROJECT_ROOT)}")
    except Exception as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
```

**Step 1: Commit**

```bash
git add workflow/cli.py
git commit -m "feat(workflow): integrate Stage 2b gap detection into planning pipeline"
```

### Task 4.3: Feed user-decisions.json into planner prompt

**Files:**
- Modify: `workflow/plan_generator.py`

In `_build_planner_prompt()`, accept an optional `user_decisions` parameter and inject it into the prompt:

```python
def _build_planner_prompt(
    context: str,
    epic_number: int,
    user_decisions: dict | None = None,  # NEW
) -> str:
```

Add a section to the prompt between the context and the planning methodology:

```python
if user_decisions:
    decisions_json = json.dumps(user_decisions, indent=2)
    prompt += f"""

---

## User Decisions (from Gap Detection)

The following decisions were made during Stage 2b gap detection. These are
binding — do not revisit or contradict them.

<user_decisions>
{decisions_json}
</user_decisions>

"""
```

In `generate_plan()`, read `user-decisions.json` if it exists:

```python
decisions_path = epic_dir / "user-decisions.json"
user_decisions = None
if decisions_path.is_file():
    user_decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
```

Pass it to `_build_planner_prompt()`.

**Step 1: Commit**

```bash
git add workflow/plan_generator.py
git commit -m "feat(workflow): feed user-decisions.json into planner prompt"
```

---

## Phase 5: Stage 4 Config Validation

**Goal:** Pre-execution validation that runs once before any story dispatch. Checks infrastructure health and agent configuration.

**Spec reference:** Stage 4 Configuration Validation section.

**Files:**
- Create: `workflow/config_validator.py`
- Modify: `workflow/orchestrator.py` (call validation before story loop)
- Test: `tests/unit/workflow/test_config_validator.py`

### Task 5.1: Create config validator module

**Files:**
- Create: `workflow/config_validator.py`

**Infrastructure checks** (run via subprocess):

| Check | Command | Pass Condition |
|-------|---------|---------------|
| Docker services | `docker compose ps --format json` | All services "running" |
| Database | `just db-check` (or similar) | Exit 0 |
| Auth tokens | Read `.gts-auth.json`, check expiry | Not expired |
| Website | `curl -sf http://localhost:9000/` | Exit 0 |
| Golden path | `just test-golden-path` | Exit 0 |

**Agent checks** (per configured agent):

| Check | Method | Pass Condition |
|-------|--------|---------------|
| Claude CLI available | `claude --version` | Exit 0 |
| Codex CLI available | `codex --version` | Exit 0 (if codex configured) |
| MCP servers load | Build MCP config, test each server | Config resolves without error |

```python
"""Stage 4 pre-execution configuration validation.

Runs infrastructure and agent checks before any story dispatch.
Hard failure on any check — no partial execution, no degraded mode.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from workflow.epic_config import EpicConfig

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ConfigValidationResult:
    """Aggregate result of all pre-execution checks."""
    passed: bool
    checks: list[CheckResult]

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


def validate_config(config: EpicConfig) -> ConfigValidationResult:
    """Run all pre-execution validation checks.

    Args:
        config: The epic configuration profile.

    Returns:
        ConfigValidationResult with pass/fail per check.
    """
    checks: list[CheckResult] = []

    checks.append(_check_docker_services())
    checks.append(_check_database())
    checks.append(_check_auth_tokens())
    checks.append(_check_website())
    checks.append(_check_golden_path())
    checks.append(_check_claude_cli())

    # Check codex if any role uses it
    models = [config.models.implementor, config.models.planner,
              config.models.plan_critic, config.models.story_critic,
              config.models.epic_critic]
    if "codex" in models:
        checks.append(_check_codex_cli())

    all_passed = all(c.passed for c in checks)
    return ConfigValidationResult(passed=all_passed, checks=checks)


def _check_docker_services() -> CheckResult:
    """Verify Docker services are running."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=15,
        )
        if result.returncode != 0:
            return CheckResult("docker_services", False, result.stderr[:200])
        return CheckResult("docker_services", True)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("docker_services", False, str(e))


def _check_database() -> CheckResult:
    """Verify database is reachable."""
    try:
        result = subprocess.run(
            ["just", "db-check"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=15,
        )
        return CheckResult("database", result.returncode == 0,
                          result.stderr[:200] if result.returncode != 0 else "")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("database", False, str(e))


def _check_auth_tokens() -> CheckResult:
    """Verify auth tokens are valid and not expired."""
    auth_file = PROJECT_ROOT.parent / ".gts-auth.json"
    if not auth_file.is_file():
        return CheckResult("auth_tokens", False, f"Auth file not found: {auth_file}")
    try:
        data = json.loads(auth_file.read_text())
        expires_at = data.get("expires_at", "")
        if expires_at:
            from datetime import datetime as dt
            expiry = dt.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry < datetime.now(UTC):
                return CheckResult("auth_tokens", False, f"Token expired at {expires_at}")
        return CheckResult("auth_tokens", True)
    except Exception as e:
        return CheckResult("auth_tokens", False, str(e))


def _check_website() -> CheckResult:
    """Verify website is reachable."""
    try:
        result = subprocess.run(
            ["curl", "-sf", "http://localhost:9000/"],
            capture_output=True, text=True, timeout=10,
        )
        return CheckResult("website", result.returncode == 0)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("website", False, str(e))


def _check_golden_path() -> CheckResult:
    """Run golden path tests to verify known-good state."""
    try:
        result = subprocess.run(
            ["just", "test-golden-path"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300,
        )
        return CheckResult("golden_path", result.returncode == 0,
                          result.stderr[-500:] if result.returncode != 0 else "")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("golden_path", False, str(e))


def _check_claude_cli() -> CheckResult:
    """Verify Claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return CheckResult("claude_cli", result.returncode == 0)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("claude_cli", False, str(e))


def _check_codex_cli() -> CheckResult:
    """Verify Codex CLI is available."""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return CheckResult("codex_cli", result.returncode == 0)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("codex_cli", False, str(e))
```

### Task 5.2: Wire config validation into orchestrator

**Files:**
- Modify: `workflow/orchestrator.py`

In `run_epic()`, before the story loop, add config validation:

```python
# After loading plan and config, before the outer loop:
from workflow.config_validator import validate_config

logger.info("Running pre-execution configuration validation...")
validation = validate_config(config)

if not validation.passed:
    for check in validation.failed_checks:
        logger.error("Config check FAILED: %s — %s", check.name, check.detail)
    epic_logger.log_event(
        "config_validation_fail",
        epic=epic_number,
        checks={c.name: {"passed": c.passed, "detail": c.detail} for c in validation.checks},
    )
    logger.error("Configuration validation failed. Fix issues and re-run.")
    sys.exit(1)

epic_logger.log_event(
    "config_validation_pass",
    epic=epic_number,
    checks={c.name: {"passed": c.passed} for c in validation.checks},
)
logger.info("Configuration validation passed.")
```

**Step 1: Commit**

```bash
git add workflow/config_validator.py workflow/orchestrator.py tests/unit/workflow/test_config_validator.py
git commit -m "feat(workflow): add Stage 4 pre-execution config validation"
```

---

## Phase 6: Stage 0 Brainstorming

**Goal:** Implement `/epic brainstorm N` as a formal skill subcommand that enriches a GitHub issue through interactive AI-assisted brainstorming.

**Files:**
- Modify: `.claude/skills/epic/SKILL.md` (add brainstorm dispatch)
- Create: `.claude/skills/epic/brainstorm.md` (brainstorm skill prompt)

### Task 6.1: Create brainstorm skill prompt

**Files:**
- Create: `.claude/skills/epic/brainstorm.md`

This is a skill file that the CC agent loads when `/epic brainstorm N` is invoked. It provides the structured brainstorming workflow:

```markdown
---
name: brainstorm
description: Interactive brainstorming to enrich a GitHub epic before it enters the pipeline.
argument-hint: "<epic-number>"
context: fork
---

# Epic Brainstorming

**Activation:** `/epic brainstorm N`

## Process

You are brainstorming to enrich GitHub issue #$ARGUMENTS into a pipeline-ready epic.

### Step 1: Read the Issue

```bash
gh issue view $ARGUMENTS --repo krazyuniks/guitar-tone-shootout
```

Read the issue body. Also read:
- `wiki/GTS-Technical-Architecture.md` — system architecture
- `AGENTS.md` — project conventions

### Step 2: Gap Detection

Identify ambiguities, assumptions, and contradictions between the issue and the architecture/codebase. Look for:
- BC ownership unclear
- Missing data model decisions
- Cross-BC messaging undefined
- Frontend layer choice ambiguous
- Auth/security requirements missing
- Testing strategy unspecified

### Step 3: Interactive Brainstorming

Ask the user questions ONE AT A TIME. For each:
- Present 2-3 options with a recommendation
- Multiple choice preferred
- Confirm each decision before proceeding
- Ask until satisfied — confirm coverage, not just exhaust a list

### Step 4: Define Observable Outcomes

For each capability in the epic, define what is observable:
- Entry point (URL, API, CLI command)
- Success state (what the user sees/gets)
- Error states (what happens on failure)
- Observer perspective (user, API, database, process)

### Step 5: Draft Enriched Epic

Write the enriched epic in this exact format:

```markdown
## Summary
One paragraph describing the feature.

## Observable Outcomes
- [ ] Outcome description (entry: ..., success: ...)
- [ ] Outcome description (observer: API, success: ...)

## Decisions
- BC ownership: ...
- Approach: ...
- Auth: ...

## Regression Boundaries
- Existing behaviour that must remain unchanged
```

### Step 6: Cross-Model Critique

Present the draft and ask: "Does this enriched epic fully specify the implementation? What's missing?"

Review the critique yourself. Refine the draft based on valid findings.

### Step 7: Human Approval

Present the final enriched epic to the user. Get explicit approval.

### Step 8: Update GitHub Issue

```bash
gh issue edit $ARGUMENTS --repo krazyuniks/guitar-tone-shootout --body "$(cat <<'EOF'
<enriched epic body here>
EOF
)"
```

**Principle:** Everything in the issue ships. No deferral, no MVP subset.
```

### Task 6.2: Update epic skill dispatch table

**Files:**
- Modify: `.claude/skills/epic/SKILL.md`

Add brainstorm to the dispatch table:

```markdown
| `brainstorm <N>`, `/epic brainstorm <N>` | Invoke the brainstorm skill: `/epic brainstorm` |
```

Note: This dispatch invokes a nested skill (`brainstorm.md`), not a `just` command. The brainstorm runs as a CC session, not a terminal process.

**Step 1: Commit**

```bash
git add .claude/skills/epic/SKILL.md .claude/skills/epic/brainstorm.md
git commit -m "feat(epic): add /epic brainstorm N skill for Stage 0"
```

---

## Phase Dependencies

```
Phase 1: Epic Config Profiles
    |
    +---> Phase 2: Dispatch Refactor (MCP + Conversation Logging)
    |         |
    |         +---> Phase 4: Stage 2b Gap Detection (uses dispatch)
    |         |
    |         +---> Phase 5: Config Validation (uses config)
    |
    +---> Phase 3: Epic Ingest Validation (independent, small)
    |
    +---> Phase 6: Stage 0 Brainstorming (independent skill)
```

Phases 3 and 6 can run in parallel with any other phase since they don't share files.

## Verification

After all phases are complete:

1. `just check` — lint, types, all existing tests pass
2. `python -m pytest tests/unit/workflow/ -v` — all new workflow tests pass
3. Manual dry-run: `./wf epic run 999` with a test issue — verify the full pipeline prompts correctly at each stage

## Files Summary

| Action | File |
|--------|------|
| Create | `workflow/epic_config.py` |
| Create | `workflow/default_config.toml` |
| Create | `workflow/conversation_logger.py` |
| Create | `workflow/gap_detection.py` |
| Create | `workflow/config_validator.py` |
| Create | `workflow/references/gap-detection-guide.md` |
| Create | `.claude/skills/epic/brainstorm.md` |
| Create | `tests/unit/workflow/test_epic_config.py` |
| Create | `tests/unit/workflow/test_conversation_logger.py` |
| Create | `tests/unit/workflow/test_epic_ingest.py` |
| Create | `tests/unit/workflow/test_config_validator.py` |
| Modify | `workflow/dispatch.py` |
| Modify | `workflow/orchestrator.py` |
| Modify | `workflow/story_executor.py` |
| Modify | `workflow/cli.py` |
| Modify | `workflow/plan_generator.py` |
| Modify | `workflow/epic_ingest.py` |
| Modify | `.claude/skills/epic/SKILL.md` |
