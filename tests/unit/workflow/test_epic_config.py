"""Tests for epic configuration loading and validation."""

import pytest

from workflow.dispatch import get_dispatch_params
from workflow.epic_config import DEFAULT_CONFIG_PATH, load_config


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

    def test_budget_timeout_defaults(self):
        """Planning and gap_detection get 1800s timeout, others get 600s."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.budgets["planning"].timeout == 1800
        assert config.budgets["gap_detection"].timeout == 1800
        assert config.budgets["implementation"].timeout == 600
        assert config.budgets["critique_plan"].timeout == 600
        assert config.budgets["critique_story"].timeout == 600
        assert config.budgets["critique_epic"].timeout == 600

    def test_mcp_planning_role_present(self):
        """MCP config has a planning entry."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert "planning" in config.mcp

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

    def test_unknown_model_key_raises(self, tmp_path):
        """Config with unknown model role raises ValueError."""
        override = tmp_path / "config.toml"
        override.write_text(
            '[models]\nreviewer = "opus"\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Unknown model role"):
            load_config(DEFAULT_CONFIG_PATH, override)


class TestGetDispatchParams:
    """get_dispatch_params() resolves MCP + timeout from config."""

    def test_none_config_returns_defaults(self):
        """None config returns (None, 600)."""
        mcp_servers, timeout = get_dispatch_params("planning", None)
        assert mcp_servers is None
        assert timeout == 600

    def test_planning_role_gets_1800(self):
        """Planning role resolves to 1800s timeout from default config."""
        config = load_config(DEFAULT_CONFIG_PATH)
        mcp_servers, timeout = get_dispatch_params("planning", config)
        assert timeout == 1800
        assert mcp_servers == ["serena", "pyright"]

    def test_critique_role_gets_600(self):
        """Critique role resolves to 600s timeout from default config."""
        config = load_config(DEFAULT_CONFIG_PATH)
        _, timeout = get_dispatch_params("critique", config)
        # critique has no budget entry, so falls back to 600
        assert timeout == 600

    def test_unknown_role_returns_defaults(self):
        """Unknown role falls back to (None, 600)."""
        config = load_config(DEFAULT_CONFIG_PATH)
        mcp_servers, timeout = get_dispatch_params("nonexistent_role", config)
        assert mcp_servers is None
        assert timeout == 600


class TestWriteConfigOverrides:
    """Test _write_config_overrides writes valid TOML."""

    def test_writes_model_overrides(self, tmp_path):
        """Model overrides are written and reloadable."""
        import shutil

        from workflow.epic_config import _write_config_overrides

        config_path = tmp_path / "config.toml"
        shutil.copy2(DEFAULT_CONFIG_PATH, config_path)

        _write_config_overrides(config_path, {"models": {"implementor": "haiku"}})

        config = load_config(DEFAULT_CONFIG_PATH, config_path)
        assert config.models.implementor == "haiku"
        # Other models unchanged
        assert config.models.planner == "opus"
        assert config.models.story_critic == "opus"

    def test_writes_budget_overrides(self, tmp_path):
        """Budget overrides are written and reloadable."""
        import shutil

        from workflow.epic_config import _write_config_overrides

        config_path = tmp_path / "config.toml"
        shutil.copy2(DEFAULT_CONFIG_PATH, config_path)

        _write_config_overrides(
            config_path,
            {"budgets": {"implementation": {"timeout": 999}}},
        )

        config = load_config(DEFAULT_CONFIG_PATH, config_path)
        assert config.budgets["implementation"].timeout == 999

    def test_roundtrip_preserves_all_sections(self, tmp_path):
        """Writing overrides preserves models, budgets, and mcp sections."""
        import shutil

        from workflow.epic_config import _write_config_overrides

        config_path = tmp_path / "config.toml"
        shutil.copy2(DEFAULT_CONFIG_PATH, config_path)

        # Write a model override
        _write_config_overrides(config_path, {"models": {"implementor": "sonnet"}})

        # Reload and verify ALL sections still exist
        config = load_config(DEFAULT_CONFIG_PATH, config_path)
        assert config.models.implementor == "sonnet"
        assert "implementation" in config.budgets
        assert "planning" in config.budgets
        assert "planning" in config.mcp

    def test_cross_model_violation_detected_on_reload(self, tmp_path):
        """Writing invalid cross-model config is caught on reload."""
        import shutil

        from workflow.epic_config import _write_config_overrides

        config_path = tmp_path / "config.toml"
        shutil.copy2(DEFAULT_CONFIG_PATH, config_path)

        # Write implementor = opus, story_critic = opus (violates constraint)
        _write_config_overrides(
            config_path,
            {"models": {"implementor": "opus", "story_critic": "opus"}},
        )

        with pytest.raises(ValueError, match="must be different"):
            load_config(DEFAULT_CONFIG_PATH, config_path)
