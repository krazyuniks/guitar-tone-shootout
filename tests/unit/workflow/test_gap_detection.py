"""Tests for gap detection module."""

import json

from workflow.gap_detection import (
    EscalatedQuestion,
    GapAnswer,
    GapReport,
    LockedDecision,
    UserDecisions,
    _parse_json_from_response,
)


class TestPydanticModels:
    """Test gap detection Pydantic models."""

    def test_locked_decision(self):
        d = LockedDecision(
            id="decision-imports-1",
            area="infrastructure",
            description="All Dockerfiles reference libs/core/",
            decision="Update all COPY lines from libs/core/ to model/gts/",
            rationale="Mechanical consequence of the rename specified in the epic",
        )
        assert d.id == "decision-imports-1"
        assert d.area == "infrastructure"

    def test_escalated_question(self):
        q = EscalatedQuestion(
            id="question-bc-1",
            area="bounded_contexts",
            description="MessageBus Protocol is a domain port but its only consumer moves to messaging.",
            question="Should MessageBus stay in domain layer or move to messaging?",
            options=[
                "Keep in model/gts/ports/ for hexagonal purity",
                "Move to infra/messaging/ to co-locate with implementation",
            ],
            recommendation=1,
            reasoning="Ports belong in the domain layer per hexagonal architecture.",
        )
        assert len(q.options) == 2
        assert q.recommendation == 1

    def test_escalated_question_requires_2_options(self):
        """Options must have 2-4 entries."""
        import pytest

        with pytest.raises(Exception):
            EscalatedQuestion(
                id="q-1",
                area="api",
                description="Gap",
                question="Question?",
                options=["only one"],
                recommendation=1,
                reasoning="Reason",
            )

    def test_gap_report(self):
        report = GapReport(
            locked_decisions=[
                LockedDecision(
                    id="d-1",
                    area="infrastructure",
                    description="Dockerfiles need updating",
                    decision="Update all COPY paths",
                    rationale="Mechanical consequence",
                ),
            ],
            escalated_questions=[
                EscalatedQuestion(
                    id="q-1",
                    area="bounded_contexts",
                    description="Protocol location",
                    question="Where should the protocol live?",
                    options=["Domain layer", "Messaging package"],
                    recommendation=1,
                    reasoning="Hexagonal architecture",
                ),
            ],
            coverage_areas_checked=["bounded_contexts", "infrastructure"],
        )
        assert len(report.locked_decisions) == 1
        assert len(report.escalated_questions) == 1
        assert len(report.coverage_areas_checked) == 2

    def test_gap_report_empty(self):
        report = GapReport()
        assert report.locked_decisions == []
        assert report.escalated_questions == []
        assert report.coverage_areas_checked == []

    def test_user_decisions(self):
        decisions = UserDecisions(
            epic_number=95,
            locked_decisions=[
                LockedDecision(
                    id="d-1",
                    area="api",
                    description="Endpoint naming",
                    decision="Follow existing /api/v1/ pattern",
                    rationale="All other endpoints use this pattern",
                ),
            ],
            answers=[
                GapAnswer(gap_id="q-1", question="Which auth?", answer="OAuth"),
            ],
            sufficiency_confirmed=True,
        )
        assert decisions.epic_number == 95
        assert len(decisions.locked_decisions) == 1
        assert len(decisions.answers) == 1
        assert decisions.sufficiency_confirmed is True

    def test_user_decisions_json_roundtrip(self):
        decisions = UserDecisions(
            epic_number=42,
            locked_decisions=[
                LockedDecision(
                    id="d-1",
                    area="infra",
                    description="Config update",
                    decision="Update all references",
                    rationale="Mechanical",
                ),
            ],
            answers=[
                GapAnswer(gap_id="q-1", question="Q1?", answer="A1"),
                GapAnswer(gap_id="q-2", question="Q2?", answer="A2"),
            ],
            sufficiency_confirmed=True,
        )
        json_str = decisions.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = UserDecisions.model_validate(parsed)
        assert restored.epic_number == 42
        assert len(restored.locked_decisions) == 1
        assert len(restored.answers) == 2
        assert restored.answers[0].answer == "A1"

    def test_user_decisions_no_locked_decisions(self):
        """Backward compat: locked_decisions defaults to empty list."""
        decisions = UserDecisions(
            epic_number=10,
            answers=[],
            sufficiency_confirmed=True,
        )
        assert decisions.locked_decisions == []


class TestParseJsonFromResponse:
    """Test JSON extraction from agent responses."""

    def test_fenced_json(self):
        text = 'Some analysis...\n```json\n{"locked_decisions": [], "escalated_questions": []}\n```\nMore text.'
        result = _parse_json_from_response(text)
        assert result == {"locked_decisions": [], "escalated_questions": []}

    def test_raw_json(self):
        text = '{"locked_decisions": [{"id": "d-1"}]}'
        result = _parse_json_from_response(text)
        assert result["locked_decisions"][0]["id"] == "d-1"

    def test_fenced_with_whitespace(self):
        text = '```json\n  {\n    "key": "value"\n  }\n```'
        result = _parse_json_from_response(text)
        assert result["key"] == "value"
