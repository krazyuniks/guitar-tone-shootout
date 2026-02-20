"""Tests for epic configuration loading and validation."""

import pytest

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

    def test_budget_defaults_present(self):
        """Each role has budget defaults."""
        config = load_config(DEFAULT_CONFIG_PATH)
        assert config.budgets["implementation"].max_turns > 0
        assert config.budgets["implementation"].max_budget_usd > 0
        assert config.budgets["planning"].max_turns > 0

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
