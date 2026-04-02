"""Tests for SourceAuthStatus value object."""

import pytest

from gts.domain.value_objects.source_auth_status import SourceAuthStatus


class TestSourceAuthStatus:
    def test_all_values_are_lowercase_strings(self) -> None:
        for member in SourceAuthStatus:
            assert member.value == member.value.lower()
            assert isinstance(member.value, str)

    def test_can_proceed_returns_true_for_valid(self) -> None:
        assert SourceAuthStatus.VALID.can_proceed() is True

    def test_can_proceed_returns_true_for_expiring_soon(self) -> None:
        assert SourceAuthStatus.EXPIRING_SOON.can_proceed() is True

    def test_can_proceed_returns_false_for_refresh_failed(self) -> None:
        assert SourceAuthStatus.REFRESH_FAILED.can_proceed() is False

    def test_can_proceed_returns_false_for_login_required(self) -> None:
        assert SourceAuthStatus.LOGIN_REQUIRED.can_proceed() is False

    def test_can_proceed_returns_false_for_unknown(self) -> None:
        assert SourceAuthStatus.UNKNOWN.can_proceed() is False

    def test_from_string_valid_value(self) -> None:
        assert SourceAuthStatus("valid") == SourceAuthStatus.VALID

    def test_from_string_unknown_value_raises(self) -> None:
        with pytest.raises(ValueError):
            SourceAuthStatus("bogus")

    def test_needs_login_true_for_login_required(self) -> None:
        assert SourceAuthStatus.LOGIN_REQUIRED.needs_login() is True

    def test_needs_login_false_for_valid(self) -> None:
        assert SourceAuthStatus.VALID.needs_login() is False
