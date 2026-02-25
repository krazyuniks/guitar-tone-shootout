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

# Available models for interactive selection
AVAILABLE_MODELS: list[str] = ["opus", "codex", "sonnet", "haiku"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "default_config.toml"


@dataclass(frozen=True)
class ModelConfig:
    """Model assignments per role."""

    planner: str = "opus"
    plan_critic: str = "opus"
    implementor: str = "codex"
    story_critic: str = "opus"
    epic_critic: str = "opus"


@dataclass(frozen=True)
class BudgetConfig:
    """Timeout for a single dispatch role."""

    timeout: int = 600  # seconds; 0 = no timeout


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
    """Enforce: execution critic models must differ from implementor.

    Planning critics (plan_critic vs planner) are NOT constrained — each
    dispatch is a fresh instance with no shared context, so same-model
    review is valid.  The constraint only applies to execution where
    the critic must not have seen the implementation context.
    """
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
    unknown_model_keys = set(models_data.keys()) - set(ModelConfig.__dataclass_fields__.keys())
    if unknown_model_keys:
        raise ValueError(f"Unknown model role(s) in config: {unknown_model_keys}")
    models = ModelConfig(**models_data)
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


def _get_available_mcp_servers() -> list[str]:
    """Return sorted list of available MCP server names."""
    from workflow.mcp import read_all_servers

    return sorted(read_all_servers().keys())


# Map from config role name → dispatch role (for tools and MCP lookup)
_ROLE_DISPATCH_MAP = {
    "implementor": "implementation",
    "story_critic": "critique",
    "epic_critic": "critique",
}

# Map from config role name → budget key
_ROLE_BUDGET_MAP = {
    "implementor": "implementation",
    "story_critic": "critique_story",
    "epic_critic": "critique_epic",
}


def prompt_execution_config(config_path: Path) -> EpicConfig:
    """Interactive model/effort/MCP selection for Stage 4 execution.

    Shows current config and lets the user override execution-phase
    models, timeouts, and MCP servers per role. Writes changes back
    to config.toml and returns the updated config.

    Args:
        config_path: Path to the epic's config.toml.

    Returns:
        Updated EpicConfig after user selections.
    """
    import typer
    from rich.console import Console
    from rich.table import Table

    from workflow.cli import flush_stdin

    console = Console()
    config = load_config(override_path=config_path)

    # Discover available MCP servers
    available_mcp = _get_available_mcp_servers()

    # Show current execution config
    table = Table(title="Stage 4 Execution Config", show_header=True)
    table.add_column("Role", style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Timeout", style="yellow")
    table.add_column("MCP Servers", style="magenta")

    for role, budget_key in _ROLE_BUDGET_MAP.items():
        model = getattr(config.models, role)
        budget = config.budgets.get(budget_key, BudgetConfig())
        dispatch_role = _ROLE_DISPATCH_MAP[role]
        mcp_servers = config.mcp.get(dispatch_role, [])
        table.add_row(
            role,
            model,
            f"{budget.timeout}s",
            ", ".join(mcp_servers) if mcp_servers else "(none)",
        )

    console.print()
    console.print(table)
    if available_mcp:
        console.print(f"\n[dim]Available MCP servers: {', '.join(available_mcp)}[/dim]")
    console.print()

    flush_stdin()
    modify = typer.confirm("Modify execution config?", default=False)
    if not modify:
        return config

    # Collect overrides
    overrides: dict[str, dict] = {"models": {}, "budgets": {}, "mcp": {}}
    available = ", ".join(AVAILABLE_MODELS)

    for role, _budget_key in _ROLE_BUDGET_MAP.items():
        dispatch_role = _ROLE_DISPATCH_MAP[role]
        current_model = getattr(config.models, role)
        current_mcp = config.mcp.get(dispatch_role, [])

        console.print(f"\n[bold]{role}[/bold] (current: {current_model})")
        console.print(f"  Available models: {available}")
        flush_stdin()
        new_model = typer.prompt("  Model", default=current_model)
        if new_model != current_model:
            overrides["models"][role] = new_model

        if available_mcp:
            current_mcp_str = ",".join(current_mcp) if current_mcp else ""
            flush_stdin()
            new_mcp_str = typer.prompt(
                "  MCP servers (comma-separated, empty for none)",
                default=current_mcp_str,
            )
            new_mcp = (
                [s.strip() for s in new_mcp_str.split(",") if s.strip()] if new_mcp_str else []
            )
            if new_mcp != current_mcp:
                overrides["mcp"][dispatch_role] = new_mcp

    # Remove empty sections
    overrides = {k: v for k, v in overrides.items() if v}

    if not overrides:
        console.print("[dim]No changes made.[/dim]")
        return config

    # Validate before writing
    models_data = {
        "planner": config.models.planner,
        "plan_critic": config.models.plan_critic,
        "implementor": config.models.implementor,
        "story_critic": config.models.story_critic,
        "epic_critic": config.models.epic_critic,
    }
    models_data.update(overrides.get("models", {}))
    test_models = ModelConfig(**models_data)
    _validate_cross_model(test_models)

    # Validate MCP server names
    if "mcp" in overrides:
        for mcp_role, servers in overrides["mcp"].items():
            unknown = [s for s in servers if s not in available_mcp]
            if unknown:
                raise ValueError(
                    f"Unknown MCP server(s) for {mcp_role}: {unknown}. Available: {available_mcp}"
                )

    # Write overrides to config.toml
    _write_config_overrides(config_path, overrides)

    # Reload and return
    updated = load_config(override_path=config_path)
    console.print("[green]Config updated.[/green]")
    return updated


def _write_config_overrides(config_path: Path, overrides: dict) -> None:
    """Write model/budget overrides to a TOML config file.

    Reads existing config, merges overrides, and writes back.
    """
    existing = _parse_toml(config_path) if config_path.is_file() else {}
    merged = _merge_dicts(existing, overrides)

    lines: list[str] = []

    # Write [models] section
    if "models" in merged:
        lines.append("[models]")
        for key, value in sorted(merged["models"].items()):
            lines.append(f'{key} = "{value}"')
        lines.append("")

    # Write [budgets.*] sections
    if "budgets" in merged:
        for role in sorted(merged["budgets"]):
            budget = merged["budgets"][role]
            if isinstance(budget, dict):
                lines.append(f"[budgets.{role}]")
                for k, v in sorted(budget.items()):
                    lines.append(f"{k} = {v}")
                lines.append("")

    # Write [mcp] section
    if "mcp" in merged:
        lines.append("[mcp]")
        for role, servers in sorted(merged["mcp"].items()):
            if isinstance(servers, list):
                server_strs = ", ".join(f'"{s}"' for s in servers)
                lines.append(f"{role} = [{server_strs}]")
        lines.append("")

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
