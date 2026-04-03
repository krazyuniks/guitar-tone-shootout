"""Tests for advisory revision failure handling in story execution."""

from __future__ import annotations

from workflow import story_executor
from workflow.artifacts import CritiqueRunArtifact, FailureClassificationArtifact


class _FakeEventLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def log_event(self, event_name: str, **payload) -> None:
        self.events.append((event_name, payload))


def test_handle_advisory_revision_failure_posts_comment_and_stops(monkeypatch) -> None:
    logger = _FakeEventLogger()
    critique_run = CritiqueRunArtifact.from_dict(
        {
            "status": "fail",
            "findings": [
                {
                    "file": "workflow/story_executor.py",
                    "line": 1200,
                    "issue": "Revision introduced a validation failure",
                    "severity": "major",
                }
            ],
            "summary": "One finding remains",
        },
        level="story",
        critique_type="story",
        critique_model="opus",
        story_id="01-sample",
        attempt=2,
    )
    classification = FailureClassificationArtifact(
        category="implementation",
        evidence="AssertionError: boom",
        pattern="assertion_error",
    )

    monkeypatch.setattr(
        story_executor,
        "comment_on_epic",
        lambda _epic_number, _body: "https://example.test/comment/1",
    )

    result = story_executor._handle_advisory_revision_failure(
        story_id="01-sample",
        attempt=2,
        critique_run=critique_run,
        classification=classification,
        error_text="AssertionError: boom",
        event_logger=logger,
        plan_scope_paths=["workflow/story_executor.py"],
        epic_number=163,
    )

    assert result is False
    assert logger.events[0][0] == "github_comment"
    assert logger.events[1][0] == "story_failed"
    assert logger.events[1][1]["reason"] == classification.terminal_reason
