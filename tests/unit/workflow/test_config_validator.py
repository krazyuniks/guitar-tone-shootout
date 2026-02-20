"""Tests for config validation result types."""

from workflow.config_validator import ConfigValidationResult, ValidationCheck


class TestValidationCheck:
    """Test ValidationCheck dataclass."""

    def test_pass_check(self):
        check = ValidationCheck("test", True)
        assert check.passed is True
        assert check.detail == ""

    def test_fail_check_with_detail(self):
        check = ValidationCheck("test", False, "something broke")
        assert check.passed is False
        assert check.detail == "something broke"


class TestConfigValidationResult:
    """Test ConfigValidationResult aggregation."""

    def test_empty_result_passes(self):
        result = ConfigValidationResult()
        assert result.passed is True

    def test_all_pass(self):
        result = ConfigValidationResult(
            checks=[
                ValidationCheck("a", True),
                ValidationCheck("b", True),
            ]
        )
        assert result.passed is True

    def test_any_fail_fails(self):
        result = ConfigValidationResult(
            checks=[
                ValidationCheck("a", True),
                ValidationCheck("b", False, "broken"),
                ValidationCheck("c", True),
            ]
        )
        assert result.passed is False

    def test_summary_format(self):
        result = ConfigValidationResult(
            checks=[
                ValidationCheck("docker", True),
                ValidationCheck("database", False, "connection refused"),
            ]
        )
        summary = result.summary()
        assert "[PASS] docker" in summary
        assert "[FAIL] database" in summary
        assert "connection refused" in summary

    def test_summary_hides_detail_on_pass(self):
        result = ConfigValidationResult(
            checks=[
                ValidationCheck("docker", True, "all good"),
            ]
        )
        summary = result.summary()
        assert "[PASS] docker" in summary
        assert "all good" not in summary
