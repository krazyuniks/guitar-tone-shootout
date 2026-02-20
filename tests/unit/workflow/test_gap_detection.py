"""Tests for gap detection module."""

import json

from workflow.gap_detection import (
    Gap,
    GapAnswer,
    GapReport,
    UserDecisions,
    _parse_json_from_response,
)


class TestPydanticModels:
    """Test gap detection Pydantic models."""

    def test_gap_minimal(self):
        gap = Gap(
            id="gap-auth-1",
            gap_type="ambiguity",
            area="security",
            description="Auth method unclear",
            question="Which auth method?",
        )
        assert gap.id == "gap-auth-1"
        assert gap.options == []
        assert gap.recommendation == ""

    def test_gap_with_options(self):
        gap = Gap(
            id="gap-bc-1",
            gap_type="bc_ownership",
            area="bounded_contexts",
            description="Unclear ownership",
            question="Which BC owns this?",
            options=["core", "audio"],
            recommendation="core",
        )
        assert len(gap.options) == 2
        assert gap.recommendation == "core"

    def test_gap_report(self):
        report = GapReport(
            gaps=[
                Gap(
                    id="gap-1",
                    gap_type="missing",
                    area="api",
                    description="Missing endpoint",
                    question="What endpoint?",
                ),
            ],
            coverage_areas_checked=["api", "frontend", "security"],
        )
        assert len(report.gaps) == 1
        assert len(report.coverage_areas_checked) == 3

    def test_gap_report_empty(self):
        report = GapReport()
        assert report.gaps == []
        assert report.coverage_areas_checked == []

    def test_user_decisions(self):
        decisions = UserDecisions(
            epic_number=95,
            answers=[
                GapAnswer(gap_id="gap-1", question="Which auth?", answer="OAuth"),
            ],
            sufficiency_confirmed=True,
        )
        assert decisions.epic_number == 95
        assert len(decisions.answers) == 1
        assert decisions.sufficiency_confirmed is True

    def test_user_decisions_json_roundtrip(self):
        decisions = UserDecisions(
            epic_number=42,
            answers=[
                GapAnswer(gap_id="gap-1", question="Q1?", answer="A1"),
                GapAnswer(gap_id="gap-2", question="Q2?", answer="A2"),
            ],
            sufficiency_confirmed=True,
        )
        json_str = decisions.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = UserDecisions.model_validate(parsed)
        assert restored.epic_number == 42
        assert len(restored.answers) == 2
        assert restored.answers[0].answer == "A1"


class TestParseJsonFromResponse:
    """Test JSON extraction from agent responses."""

    def test_fenced_json(self):
        text = 'Some analysis...\n```json\n{"gaps": []}\n```\nMore text.'
        result = _parse_json_from_response(text)
        assert result == {"gaps": []}

    def test_raw_json(self):
        text = '{"gaps": [{"id": "gap-1"}]}'
        result = _parse_json_from_response(text)
        assert result["gaps"][0]["id"] == "gap-1"

    def test_fenced_with_whitespace(self):
        text = '```json\n  {\n    "key": "value"\n  }\n```'
        result = _parse_json_from_response(text)
        assert result["key"] == "value"
