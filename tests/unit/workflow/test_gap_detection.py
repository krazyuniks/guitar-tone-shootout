"""Tests for gap detection module."""

import json

from workflow.gap_detection import (
    CritiqueReport,
    EscalatedQuestion,
    FalseEscalation,
    GapAnswer,
    GapReport,
    LockedDecision,
    UserDecisions,
    _parse_json_from_response,
    apply_critique,
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


class TestCritiqueReport:
    """Test critique report model."""

    def test_critique_report_with_false_escalations(self):
        report = CritiqueReport(
            false_escalations=[
                FalseEscalation(
                    question_id="question-structure-3",
                    reason="Epic explicitly specifies the rename",
                    locked_decision="Rename to gts-domain as epic specifies",
                ),
            ],
            verdict="fail",
        )
        assert len(report.false_escalations) == 1
        assert report.verdict == "fail"

    def test_critique_report_pass(self):
        report = CritiqueReport(false_escalations=[], verdict="pass")
        assert report.false_escalations == []
        assert report.verdict == "pass"


class TestApplyCritique:
    """Test false escalation demotion logic."""

    def _make_gap_report(self) -> GapReport:
        return GapReport(
            locked_decisions=[
                LockedDecision(
                    id="decision-infra-1",
                    area="infrastructure",
                    description="Dockerfiles need updating",
                    decision="Update all COPY paths",
                    rationale="Mechanical consequence",
                ),
            ],
            escalated_questions=[
                EscalatedQuestion(
                    id="question-bc-1",
                    area="bounded_contexts",
                    description="Protocol location unclear",
                    question="Where should the protocol live?",
                    options=["Domain layer", "Messaging package"],
                    recommendation=1,
                    reasoning="Hexagonal architecture",
                ),
                EscalatedQuestion(
                    id="question-structure-2",
                    area="structure",
                    description="Package naming convention",
                    question="Should we use underscores or hyphens?",
                    options=["Underscores", "Hyphens"],
                    recommendation=1,
                    reasoning="PEP 8 convention",
                ),
            ],
            coverage_areas_checked=["bounded_contexts", "infrastructure", "structure"],
        )

    def test_demotes_false_escalation(self):
        gap_report = self._make_gap_report()
        critique = CritiqueReport(
            false_escalations=[
                FalseEscalation(
                    question_id="question-structure-2",
                    reason="Codebase already uses underscores everywhere",
                    locked_decision="Use underscores per existing convention",
                ),
            ],
            verdict="fail",
        )
        result = apply_critique(gap_report, critique)

        # Original unchanged
        assert len(gap_report.escalated_questions) == 2

        # Result has one fewer escalated question
        assert len(result.escalated_questions) == 1
        assert result.escalated_questions[0].id == "question-bc-1"

        # And one more locked decision
        assert len(result.locked_decisions) == 2
        demoted = result.locked_decisions[1]
        assert demoted.id == "decision-structure-2"
        assert demoted.area == "structure"
        assert demoted.decision == "Use underscores per existing convention"
        assert "Demoted by critique" in demoted.rationale

    def test_no_false_escalations(self):
        gap_report = self._make_gap_report()
        critique = CritiqueReport(false_escalations=[], verdict="pass")
        result = apply_critique(gap_report, critique)

        assert len(result.escalated_questions) == 2
        assert len(result.locked_decisions) == 1

    def test_unknown_question_id_skipped(self):
        gap_report = self._make_gap_report()
        critique = CritiqueReport(
            false_escalations=[
                FalseEscalation(
                    question_id="question-nonexistent-99",
                    reason="Doesn't exist",
                    locked_decision="Irrelevant",
                ),
            ],
            verdict="fail",
        )
        result = apply_critique(gap_report, critique)

        # Nothing changed — unknown ID was skipped
        assert len(result.escalated_questions) == 2
        assert len(result.locked_decisions) == 1

    def test_multiple_demotions(self):
        gap_report = self._make_gap_report()
        critique = CritiqueReport(
            false_escalations=[
                FalseEscalation(
                    question_id="question-bc-1",
                    reason="Epic specifies domain layer",
                    locked_decision="Keep in domain layer as epic specifies",
                ),
                FalseEscalation(
                    question_id="question-structure-2",
                    reason="Codebase convention is clear",
                    locked_decision="Use underscores",
                ),
            ],
            verdict="fail",
        )
        result = apply_critique(gap_report, critique)

        assert len(result.escalated_questions) == 0
        assert len(result.locked_decisions) == 3
