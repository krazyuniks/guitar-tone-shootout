"""Tests for code review fixes (PR #118 follow-up).

Each test class targets one specific fix from the code review findings.
"""

import pytest

from workflow.config_validator import (
    ConfigValidationResult,
    ValidationCheck,
    check_database,
    check_golden_path,
    check_website,
    validate_config,
)
from workflow.dispatch import get_adapter
from workflow.epic_config import DEFAULT_CONFIG_PATH, BudgetConfig, load_config
from workflow.epic_ingest import validate_epic_structure

# ---------------------------------------------------------------------------
# Fix 1: validate_config() is importable and callable
# ---------------------------------------------------------------------------


class TestValidateConfigWiring:
    """Fix 1: validate_config() must be importable from config_validator
    and callable with a project root path."""

    def test_validate_config_importable_from_orchestrator(self):
        """The orchestrator imports validate_config at module level."""
        from workflow.orchestrator import validate_config as vc

        assert callable(vc)

    def test_validate_config_returns_result(self, tmp_path):
        """validate_config returns a ConfigValidationResult even when
        commands aren't found (FileNotFoundError handling)."""
        result = validate_config(tmp_path, skip_golden_path=True)
        assert isinstance(result, ConfigValidationResult)
        assert len(result.checks) >= 3  # docker, database, auth, website


# ---------------------------------------------------------------------------
# Fix 2: plan_verifier adapter auto-selection
# ---------------------------------------------------------------------------


class TestPlanVerifierAdapterSelection:
    """Fix 2: plan_verifier no longer hardcodes get_codex_adapter().
    dispatch_agent auto-selects via get_adapter(model)."""

    def test_get_codex_adapter_not_imported(self):
        """get_codex_adapter should not be imported by plan_verifier."""
        import workflow.plan_verifier as pv

        # The import was removed — verify it's not in the module namespace
        assert not hasattr(pv, "get_codex_adapter")

    def test_get_adapter_routes_codex(self):
        """get_adapter('codex') returns a CodexAdapter."""
        from workflow.dispatch import CodexAdapter

        adapter = get_adapter("codex")
        assert isinstance(adapter, CodexAdapter)

    def test_get_adapter_routes_opus(self):
        """get_adapter('opus') returns a ClaudeAdapter."""
        from workflow.dispatch import ClaudeAdapter

        adapter = get_adapter("opus")
        assert isinstance(adapter, ClaudeAdapter)

    def test_verify_plan_signature_no_adapter_param(self):
        """verify_plan() should not pass an explicit adapter kwarg to
        dispatch_agent — it relies on auto-selection."""
        import inspect

        from workflow.plan_verifier import verify_plan

        source = inspect.getsource(verify_plan)
        assert "adapter=get_codex_adapter" not in source
        assert "adapter=" not in source


# ---------------------------------------------------------------------------
# Fix 3: gap detection budget resolution
# ---------------------------------------------------------------------------


class TestGapDetectionBudgetConfig:
    """gap_detection uses the planning budget (no separate entry needed)."""

    def test_gap_detection_uses_planning_budget(self):
        """gap_detection falls back to planning budget timeout."""
        config = load_config(DEFAULT_CONFIG_PATH)
        # gap_detection no longer has its own budget entry;
        # it uses the planning budget via get_dispatch_params fallback
        assert "planning" in config.budgets
        budget = config.budgets["planning"]
        assert isinstance(budget, BudgetConfig)
        assert budget.timeout > 0


# ---------------------------------------------------------------------------
# Fix 4: checkbox scoped to Observable Outcomes
# ---------------------------------------------------------------------------


class TestCheckboxScoping:
    """Fix 4: checkbox check is scoped to Observable Outcomes section,
    not the entire body."""

    def test_checkbox_only_in_outcomes_passes(self):
        body = """\
## Summary
A feature.

## Observable Outcomes
- [ ] User can see something

## Decisions
- Some decision

## Regression Boundaries
- Existing stuff
"""
        errors = validate_epic_structure(body)
        assert not any("checkbox" in e.lower() for e in errors)

    def test_checkbox_in_other_section_fails(self):
        """A checkbox in Decisions should NOT satisfy Observable Outcomes."""
        body = """\
## Summary
A feature.

## Observable Outcomes
- User can see something

## Decisions
- [ ] Decide later

## Regression Boundaries
- Existing stuff
"""
        errors = validate_epic_structure(body)
        assert any("checkbox" in e.lower() for e in errors)

    def test_no_observable_outcomes_section_skips_checkbox_check(self):
        """If Observable Outcomes section is missing entirely,
        we get a 'missing section' error, not a checkbox error."""
        body = """\
## Summary
A feature.

## Decisions
- [ ] Something

## Regression Boundaries
- Existing stuff
"""
        errors = validate_epic_structure(body)
        # Missing section error
        assert any("Observable Outcomes" in e for e in errors)
        # Should NOT additionally report checkbox error (section doesn't exist)
        assert not any("checkbox" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Fix 5: load_config() error handling
# ---------------------------------------------------------------------------


class TestLoadConfigErrorHandling:
    """Fix 5: load_config() errors are caught at CLI boundaries."""

    def test_invalid_toml_raises_value_error(self, tmp_path):
        """Malformed TOML raises a clean error, not a raw traceback."""
        bad_toml = tmp_path / "bad.toml"
        bad_toml.write_text("this is not valid [toml", encoding="utf-8")
        with pytest.raises(Exception):  # tomllib.TOMLDecodeError
            load_config(default_path=bad_toml)

    def test_missing_default_path_raises(self, tmp_path):
        """Non-existent default config raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(default_path=tmp_path / "nonexistent.toml")

    def test_same_model_cross_role_warns(self, tmp_path, caplog):
        """Same model for critic and implementor logs a warning (not an error)."""
        override = tmp_path / "config.toml"
        override.write_text(
            '[models]\nimplementor = "opus"\nstory_critic = "opus"\n',
            encoding="utf-8",
        )
        import logging

        with caplog.at_level(logging.WARNING, logger="workflow.epic_config"):
            config = load_config(DEFAULT_CONFIG_PATH, override)
        assert config.models.implementor == "opus"
        assert "story_critic and implementor are both opus" in caplog.text


# ---------------------------------------------------------------------------
# Fix 6: preflight check FileNotFoundError handling
# ---------------------------------------------------------------------------


class TestPreflightFileNotFoundHandling:
    """Fix 6: check_database(), check_website(), check_golden_path()
    all handle FileNotFoundError gracefully."""

    def test_check_database_missing_docker(self, tmp_path, monkeypatch):
        """check_database returns a failed ValidationCheck when docker
        command is not found (simulated via empty PATH)."""
        monkeypatch.setenv("PATH", str(tmp_path))
        result = check_database(tmp_path)
        assert isinstance(result, ValidationCheck)
        assert result.passed is False
        assert "not found" in result.detail

    def test_check_website_missing_docker(self, tmp_path, monkeypatch):
        """check_website returns a failed ValidationCheck when docker
        command is not found."""
        monkeypatch.setenv("PATH", str(tmp_path))
        result = check_website(tmp_path)
        assert isinstance(result, ValidationCheck)
        assert result.passed is False
        assert "not found" in result.detail

    def test_check_golden_path_missing_just(self, tmp_path, monkeypatch):
        """check_golden_path returns a failed ValidationCheck when just
        command is not found."""
        monkeypatch.setenv("PATH", str(tmp_path))
        result = check_golden_path(tmp_path)
        assert isinstance(result, ValidationCheck)
        assert result.passed is False
        assert "not found" in result.detail


class TestEpic163WorkflowFixes:
    """Regression coverage for workflow-system fixes under Epic 163."""

    def test_story_executor_no_longer_runtime_imports_orchestrator_for_comments(self):
        import inspect

        from workflow import story_executor

        source = inspect.getsource(story_executor._post_story_critique_findings_comment)
        assert "from workflow.orchestrator" not in source
