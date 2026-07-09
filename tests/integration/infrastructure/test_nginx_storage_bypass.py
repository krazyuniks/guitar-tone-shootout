"""nginx must not expose storage paths outside the gated media handler."""

import re
from pathlib import Path

TEMPLATE = Path("/app/infrastructure/nginx/nginx.conf.template")


def _location_blocks(content: str) -> dict[str, str]:
    """Map location expression -> block body (flat parse; no nested locations)."""
    blocks: dict[str, str] = {}
    for match in re.finditer(r"location\s+([^\s{]+(?:\s+[^\s{]+)?)\s*\{([^}]*)\}", content):
        blocks[match.group(1)] = match.group(2)
    return blocks


def _assert_uniform_storage_404(blocks: dict[str, str], location: str) -> None:
    assert location in blocks, f"nginx must explicitly block {location}"
    body = blocks[location]
    assert "return 404" in body, f"{location} must return a uniform 404"
    assert "proxy_pass" not in body, f"{location} must not reach any upstream"
    assert "root " not in body and "alias " not in body, f"{location} must not serve static files"


def test_app_storage_prefix_is_blocked_before_app_spa() -> None:
    blocks = _location_blocks(TEMPLATE.read_text())
    _assert_uniform_storage_404(blocks, "/app/storage/")


def test_app_storage_exact_uri_is_blocked() -> None:
    blocks = _location_blocks(TEMPLATE.read_text())
    _assert_uniform_storage_404(blocks, "= /app/storage")
