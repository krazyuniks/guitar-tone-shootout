"""Shootout cards derive readiness from lifecycle state, not montage availability."""

from pathlib import Path


def test_completed_card_is_not_gated_by_master_output_path() -> None:
    content = Path("/app/frontend/astro/dist/fragments/shootouts/shootout_card.html").read_text()

    assert "shootout.status == 'completed'" in content
    assert "shootout.status == 'completed' and shootout.output_path" not in content
