"""Locate a system Chrome or Chromium executable."""

from __future__ import annotations

import shutil

CHROMIUM_EXECUTABLES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def find_chromium_executable(path: str | None = None) -> str | None:
    """Return the first supported Chrome or Chromium executable on PATH."""
    for executable in CHROMIUM_EXECUTABLES:
        if resolved := shutil.which(executable, path=path):
            return resolved
    return None
