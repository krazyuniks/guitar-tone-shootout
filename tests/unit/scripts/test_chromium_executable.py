"""Tests for system Chromium executable discovery."""

from pathlib import Path

from scripts.chromium_executable import find_chromium_executable


def _make_executable(directory: Path, name: str) -> Path:
    executable = directory / name
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_finds_google_chrome_stable(tmp_path: Path) -> None:
    expected = _make_executable(tmp_path, "google-chrome-stable")

    assert find_chromium_executable(path=str(tmp_path)) == str(expected)


def test_prefers_stable_chrome_to_chromium(tmp_path: Path) -> None:
    expected = _make_executable(tmp_path, "google-chrome-stable")
    _make_executable(tmp_path, "chromium")

    assert find_chromium_executable(path=str(tmp_path)) == str(expected)


def test_returns_none_when_no_supported_browser_exists(tmp_path: Path) -> None:
    assert find_chromium_executable(path=str(tmp_path)) is None
