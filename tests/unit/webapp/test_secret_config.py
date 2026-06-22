"""Tests for application secret configuration."""

from __future__ import annotations

import pytest

from webapp.config.secrets import DEV_SECRET_KEY, get_app_secret_key


def test_development_allows_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    assert get_app_secret_key() == DEV_SECRET_KEY


def test_production_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_app_secret_key()


@pytest.mark.parametrize(
    "secret_key",
    ["dev-secret-key-change-in-production", "dev_secret_key_change_in_production"],
)
def test_production_rejects_default_secret(
    monkeypatch: pytest.MonkeyPatch, secret_key: str
) -> None:
    monkeypatch.setenv("SECRET_KEY", secret_key)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_app_secret_key()


def test_production_allows_explicit_non_default_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "real-secret-value")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    assert get_app_secret_key() == "real-secret-value"
