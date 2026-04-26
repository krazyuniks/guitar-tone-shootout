"""Unit tests for woof/lib/audit_filter.py.

Outcome coverage:
  O1 — secret-shaped spans are replaced with [REDACTED:<reason>] before the
       output file lands on disk.
  O2 — subprocess stdout exceeding the per-file cap is truncated; the full
       output overflows to the gitignored audit/raw/ path.
  O3 — the operator can disable both filters via agents.toml [audit].enabled.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_FILTER_PATH = REPO_ROOT / "woof" / "lib" / "audit_filter.py"

pytestmark = pytest.mark.host_only


def _load_module():
    loader = SourceFileLoader("audit_filter", str(AUDIT_FILTER_PATH))
    spec = importlib.util.spec_from_loader("audit_filter", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_filter"] = mod
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# O1 — redaction of built-in secret patterns
# ---------------------------------------------------------------------------


def test_jwt_redacted() -> None:
    """O1: a JWT in the output is replaced with [REDACTED:jwt]."""
    mod = _load_module()
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    result = mod.redact(f"Authorization: Bearer {jwt}")
    assert jwt not in result
    assert "[REDACTED:jwt]" in result


def test_aws_access_key_redacted() -> None:
    """O1: an AWS access key is replaced with [REDACTED:aws-access-key]."""
    mod = _load_module()
    key = "AKIAIOSFODNN7EXAMPLE"
    result = mod.redact(f"aws_access_key_id = {key}")
    assert key not in result
    assert "[REDACTED:aws-access-key]" in result


def test_bearer_token_redacted() -> None:
    """O1: a Bearer token value in an auth header is redacted."""
    mod = _load_module()
    line = "Authorization: Bearer ghp_16C7e42F292c6912E7710c838347Ae178B4a"
    result = mod.redact(line)
    assert "ghp_16C7e42F292c6912E7710c838347Ae178B4a" not in result
    assert "[REDACTED:bearer-token]" in result


# ---------------------------------------------------------------------------
# O2 — size cap truncation
# ---------------------------------------------------------------------------


def test_size_cap_truncates_and_writes_raw(tmp_path: Path) -> None:
    """O2: output exceeding max_bytes is truncated to exactly <= max_bytes; raw file is written."""
    mod = _load_module()
    text = "x" * 2000
    max_bytes = 100
    raw_path = tmp_path / "raw" / "cld-story-executor-20260101T000000Z.output"
    committed = mod.apply_size_cap(text, max_bytes=max_bytes, raw_path=raw_path, epic_id=181)

    assert len(committed.encode("utf-8")) <= max_bytes
    assert "truncated" in committed
    assert "audit/raw/" in committed
    assert raw_path.is_file()
    assert raw_path.read_text() == text


def test_size_cap_multibyte_boundary(tmp_path: Path) -> None:
    """O2: truncation at a multibyte UTF-8 boundary never exceeds max_bytes.

    Euro sign (€) is 3 bytes in UTF-8. Slicing at an arbitrary byte offset
    can land mid-character; the cap must still hold.
    """
    mod = _load_module()
    text = "€" * 1000  # 3000 bytes
    max_bytes = 80
    raw_path = tmp_path / "raw" / "mb.output"
    committed = mod.apply_size_cap(text, max_bytes=max_bytes, raw_path=raw_path, epic_id=181)

    assert len(committed.encode("utf-8")) <= max_bytes
    assert "truncated" in committed
    assert raw_path.read_text() == text


# ---------------------------------------------------------------------------
# O3 — operator-configurable filter (enabled=False disables both filters)
# ---------------------------------------------------------------------------


def test_enabled_false_passthrough(tmp_path: Path) -> None:
    """O3: enabled=False returns text unchanged; no raw file is written."""
    mod = _load_module()
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    raw_path = tmp_path / "raw" / "output"
    result = mod.filter_audit_output(
        jwt,
        enabled=False,
        max_bytes=10,
        redact_patterns=(),
        raw_path=raw_path,
        epic_id=181,
    )
    assert result == jwt
    assert not raw_path.exists()


def test_custom_pattern_redacted() -> None:
    """O3: extra_patterns supplied by the operator are applied after built-ins."""
    mod = _load_module()
    text = "DB_PASSWORD=supersecret123"
    result = mod.redact(text, extra_patterns=("DB_PASSWORD=\\S+",))
    assert "supersecret123" not in result
    assert "[REDACTED:custom]" in result
