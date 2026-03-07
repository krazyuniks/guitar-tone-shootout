"""Tests for unified dispatch logging and streaming dispatch configuration."""

import json

from workflow.dispatch import ClaudeAdapter
from workflow.dispatch_log import DispatchLog, token_summary


class TestClaudeAdapterStreaming:
    """Claude adapter should switch to stream-json for streaming dispatches."""

    def test_streaming_mode_uses_stream_json_output(self) -> None:
        adapter = ClaudeAdapter()

        args = adapter.build_args(
            model="sonnet",
            json_schema=None,
            mcp_servers=[],
            streaming=True,
        )

        output_idx = args.index("--output-format")
        assert args[output_idx + 1] == "stream-json"
        assert "--verbose" in args


class TestDispatchLogLifecycle:
    """DispatchLog should expose started and completed lifecycle entries."""

    def test_start_and_complete_entries_share_dispatch_id(self, tmp_path) -> None:
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        log = DispatchLog(epic_dir, "run-1")

        dispatch = log.start_dispatch(
            role="planner",
            model="sonnet",
            prompt="plan this",
        )
        log.record(
            dispatch=dispatch,
            role="planner",
            model="sonnet",
            prompt="plan this",
            output='{"status":"ok"}',
            success=True,
            exit_code=0,
            turns=3,
            duration_ms=2500,
        )

        entries = [
            json.loads(line)
            for line in (epic_dir / "dispatch.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert [entry["status"] for entry in entries] == ["started", "completed"]
        assert entries[0]["dispatch_id"] == entries[1]["dispatch_id"]
        assert entries[1]["conversation_file"].endswith("-conversation.jsonl")
        assert (epic_dir / entries[0]["prompt_file"]).exists()
        assert (epic_dir / entries[1]["response_file"]).exists()

    def test_token_summary_counts_completed_entries_only(self, tmp_path) -> None:
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        log = DispatchLog(epic_dir, "run-1")

        dispatch = log.start_dispatch(
            role="planner",
            model="sonnet",
            prompt="plan this",
        )
        log.record(
            dispatch=dispatch,
            role="planner",
            model="sonnet",
            prompt="plan this",
            output="done",
            success=True,
            exit_code=0,
            turns=1,
            duration_ms=1000,
        )

        summary = token_summary(epic_dir, "run-1")

        assert "planner" in summary
        assert "1" in summary
