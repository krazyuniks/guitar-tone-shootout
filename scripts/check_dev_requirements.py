"""Development requirements checking.

Checks for development requirements needed for the full development workflow:
- Playwright for E2E tests
- Chrome DevTools MCP and Playwright MCP for UI debugging
- GLM Vision MCP (optional, for GLM model users)

NOTE: This module only CHECKS requirements. Installation is handled by `just infra`.
"""

import json
import shutil
import subprocess
from pathlib import Path

# Cache for cld wrapper check (checked once per run)
_cld_available: bool | None = None


def check_cld_wrapper_available() -> bool:
    """Check if the cld wrapper script is available.

    The cld wrapper allows on-demand MCP server enabling via command line
    (e.g., `opus cp` enables both chrome-devtools and playwright MCP).
    """
    global _cld_available
    if _cld_available is None:
        _cld_available = shutil.which("cld") is not None
    return _cld_available


def check_all_requirements() -> dict[str, bool]:
    """Check all development requirements.

    Returns dict of {requirement: is_satisfied}.
    """
    return {
        "chrome": check_chrome_installed(),
        "playwright": check_playwright_installed(),
        "chrome_devtools_mcp": check_mcp_server_configured("chrome-devtools"),
        "playwright_mcp": check_mcp_server_configured("playwright"),
        "glm_vision_mcp": check_mcp_server_configured("glm-vision"),
    }


def check_chrome_installed() -> bool:
    """Check if Chrome or Chromium is installed on the system.

    Required for Chrome DevTools MCP to function. Checks for:
    - Linux: google-chrome, chromium, chromium-browser in PATH
    - macOS: Google Chrome.app or Chromium.app bundles, or CLI tools in PATH
    """
    import platform

    # Check CLI executables (works on both platforms)
    chrome_executables = ["google-chrome", "chromium", "chromium-browser"]
    for exe in chrome_executables:
        if shutil.which(exe):
            return True

    # On macOS, also check for .app bundles
    if platform.system() == "Darwin":
        macos_apps = [
            Path("/Applications/Google Chrome.app"),
            Path("/Applications/Chromium.app"),
            Path.home() / "Applications" / "Google Chrome.app",
            Path.home() / "Applications" / "Chromium.app",
        ]
        for app in macos_apps:
            if app.exists():
                return True

    return False


def check_playwright_installed() -> bool:
    """Check if Playwright browser is installed and can actually run.

    This checks both:
    1. Browser files exist in Playwright cache directory
    2. System dependencies are installed (can actually launch)

    Playwright cache locations:
    - Linux: ~/.cache/ms-playwright/
    - macOS: ~/Library/Caches/ms-playwright/
    """
    import platform

    # Playwright cache location varies by platform
    if platform.system() == "Darwin":
        playwright_cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        playwright_cache = Path.home() / ".cache" / "ms-playwright"

    if not playwright_cache.exists():
        return False

    chromium_dirs = list(playwright_cache.glob("chromium-*"))
    if not chromium_dirs:
        return False

    # Browser files exist, but can it actually run?
    # Try to launch playwright and immediately close it
    e2e_dir = Path.cwd() / "tests" / "e2e" / "python"
    if not e2e_dir.exists():
        # Not in a worktree with E2E tests, just check files exist
        return True

    try:
        # Run a quick playwright check that verifies browser can launch
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from playwright.sync_api import sync_playwright; "
                "p = sync_playwright().start(); "
                "b = p.chromium.launch(headless=True); "
                "b.close(); p.stop(); "
                "print('ok')",
            ],
            cwd=e2e_dir,
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0 and b"ok" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # If we can't run the check, fall back to just checking files exist
        return True


def check_mcp_server_configured(server_name: str) -> bool:
    """Check if an MCP server is available.

    Checks in order:
    1. cld wrapper (enables MCP on-demand via `opus cp`, `sonnet c`, etc.)
    2. Project-level .mcp.json
    3. Global ~/.claude/settings.json

    Args:
        server_name: The name of the MCP server to check for
    """
    # If cld wrapper is available, MCP can be enabled on-demand
    # cld supports chrome-devtools and playwright
    if check_cld_wrapper_available() and server_name in ("chrome-devtools", "playwright"):
        return True

    # Check project-level .mcp.json
    project_mcp = Path.cwd() / ".mcp.json"
    if project_mcp.exists():
        try:
            config = json.loads(project_mcp.read_text())
            mcp_servers = config.get("mcpServers", {})
            if server_name in mcp_servers:
                return True
        except (json.JSONDecodeError, KeyError):
            pass

    # Check global Claude settings
    claude_config = Path.home() / ".claude" / "settings.json"
    if claude_config.exists():
        try:
            settings = json.loads(claude_config.read_text())
            mcp_servers = settings.get("mcpServers", {})
            if server_name in mcp_servers:
                return True
        except (json.JSONDecodeError, KeyError):
            pass

    return False


def main() -> int:
    """Print each dev requirement and its status; exit non-zero if any are missing."""
    import sys

    results = check_all_requirements()
    missing = []
    for name, ok in results.items():
        print(f"  {name:20s} {'ok' if ok else 'MISSING'}")
        if not ok:
            missing.append(name)
    if missing:
        print(f"\nmissing: {', '.join(missing)} (install with `just infra`)", file=sys.stderr)
        return 1
    print("\nall dev requirements satisfied")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
