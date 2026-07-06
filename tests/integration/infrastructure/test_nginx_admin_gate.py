"""The unauthenticated admin API must never be reachable through the public proxy.

The admin router mounts at /api/admin/* and carries no authentication by design:
access control is the network boundary. nginx must therefore 404 the prefix
externally. A bare /admin/ block does not do this - nginx prefix matching sends
/api/admin/* to the longer /api/ proxy match - so these tests pin the exact
location that closes the hole.
"""

import re
from pathlib import Path

TEMPLATE = Path("/app/infrastructure/nginx/nginx.conf.template")


def _location_blocks(content: str) -> dict[str, str]:
    """Map location expression -> block body (flat parse; no nested locations)."""
    blocks: dict[str, str] = {}
    for match in re.finditer(r"location\s+([^\s{]+(?:\s+[^\s{]+)?)\s*\{([^}]*)\}", content):
        blocks[match.group(1)] = match.group(2)
    return blocks


def test_api_admin_prefix_is_blocked() -> None:
    blocks = _location_blocks(TEMPLATE.read_text())
    assert "/api/admin/" in blocks, (
        "nginx must define location /api/admin/ - a bare /admin/ block never "
        "matches the real /api/admin/* router prefix"
    )
    body = blocks["/api/admin/"]
    assert "return 404" in body, "the admin prefix must 404 externally"
    assert "proxy_pass" not in body, "the admin prefix must never be proxied"


def test_api_admin_exact_uri_is_blocked() -> None:
    """A trailing-slash prefix location misses the slashless /api/admin URI."""
    blocks = _location_blocks(TEMPLATE.read_text())
    assert "= /api/admin" in blocks, (
        "nginx must define location = /api/admin - the /api/admin/ prefix "
        "block does not match the exact slashless URI"
    )
    body = blocks["= /api/admin"]
    assert "return 404" in body
    assert "proxy_pass" not in body


def test_no_stale_admin_block() -> None:
    """The old /admin/ block matched nothing the webapp serves; it must be gone."""
    blocks = _location_blocks(TEMPLATE.read_text())
    assert "/admin/" not in blocks, (
        "stale location /admin/ found - the webapp has no /admin/* routes; "
        "the real surface is /api/admin/*"
    )


def test_api_proxy_still_present() -> None:
    """The general API proxy must survive the admin carve-out."""
    blocks = _location_blocks(TEMPLATE.read_text())
    assert "/api/" in blocks
    assert "proxy_pass" in blocks["/api/"]
