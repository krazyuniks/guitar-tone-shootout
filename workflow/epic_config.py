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
            f"plan_critic ({models.plan_critic}) must be different from planner ({models.planner})"
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
