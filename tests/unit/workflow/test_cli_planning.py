from pathlib import Path
from types import SimpleNamespace

from workflow import cli
from workflow.artifacts import PlanVerificationResultArtifact


class _RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def log_event(self, event_name: str, **payload) -> None:
        self.events.append((event_name, payload))


def _write_planning_inputs(epic_dir: Path) -> None:
    epic_dir.mkdir(parents=True)
    (epic_dir / "EPIC.md").write_text("# Epic\n", encoding="utf-8")
    (epic_dir / "repo_facts.json").write_text("{}", encoding="utf-8")
    (epic_dir / "curation.json").write_text("{}", encoding="utf-8")
    (epic_dir / "CURATION.md").write_text("# Curation\n", encoding="utf-8")
    (epic_dir / "plan.json").write_text("{}", encoding="utf-8")
    (epic_dir / "PLAN.md").write_text("# Plan\n", encoding="utf-8")


def test_run_planning_steps_skips_decision_gate_after_revision_success(
    monkeypatch, tmp_path
) -> None:
    project_root = tmp_path
    epic_dir = project_root / ".planning" / "epics" / "E155"
    _write_planning_inputs(epic_dir)
    logger = _RecordingLogger()
    config = SimpleNamespace(models=SimpleNamespace(plan_critic="codex", planner="opus"))

    monkeypatch.setattr(cli, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(cli, "_should_skip", lambda _path, _label: True)

    def fake_verify_with_revision_cycle(_epic_dir: Path, config=None):
        _ = config
        return (PlanVerificationResultArtifact.from_revision_success(), True)

    monkeypatch.setattr(
        "workflow.plan_verifier.verify_with_revision_cycle",
        fake_verify_with_revision_cycle,
    )
    monkeypatch.setattr(
        "workflow.plan_verifier.present_decision_gate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("decision gate should not run")
        ),
    )
    monkeypatch.setattr("workflow.git_helpers.robust_commit", lambda _msg, _paths: "abc123")
    monkeypatch.setattr("workflow.git_helpers.git_sync", lambda: None)

    outcome = cli._run_planning_steps(155, epic_dir, config, logger)

    assert outcome == cli.PlanningPipelineOutcome.COMMITTED
    assert [event for event, _payload in logger.events] == [
        "phase_a_pass",
        "phase_b_pass",
        "plan_committed",
    ]
