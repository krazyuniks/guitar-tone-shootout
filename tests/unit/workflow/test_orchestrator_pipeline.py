"""Tests for top-level epic pipeline control flow."""

from workflow import cli, orchestrator


def test_run_pipeline_continues_into_execution_after_planning_commit(monkeypatch, tmp_path) -> None:
    planning_dir = tmp_path / ".planning" / "epics"
    planning_dir.mkdir(parents=True)
    (planning_dir / "E155").mkdir()

    calls: list[tuple[int, bool]] = []

    monkeypatch.setattr(orchestrator, "PLANNING_DIR", planning_dir)
    monkeypatch.setattr(cli, "_check_plan_committed", lambda _epic_dir: False)
    monkeypatch.setattr(
        cli,
        "_run_planning_pipeline",
        lambda _epic_number: cli.PlanningPipelineOutcome.COMMITTED,
    )
    monkeypatch.setattr(
        orchestrator,
        "run_epic",
        lambda epic_number, resume=False: calls.append((epic_number, resume)),
    )

    orchestrator.run_pipeline(155)

    assert calls == [(155, True)]


def test_run_pipeline_stops_when_planning_does_not_commit(monkeypatch, tmp_path) -> None:
    planning_dir = tmp_path / ".planning" / "epics"
    planning_dir.mkdir(parents=True)
    (planning_dir / "E155").mkdir()

    calls: list[tuple[int, bool]] = []

    monkeypatch.setattr(orchestrator, "PLANNING_DIR", planning_dir)
    monkeypatch.setattr(cli, "_check_plan_committed", lambda _epic_dir: False)
    monkeypatch.setattr(
        cli,
        "_run_planning_pipeline",
        lambda _epic_number: cli.PlanningPipelineOutcome.STOPPED_AT_GATE,
    )
    monkeypatch.setattr(
        orchestrator,
        "run_epic",
        lambda epic_number, resume=False: calls.append((epic_number, resume)),
    )

    orchestrator.run_pipeline(155)

    assert calls == []
