"""Tests for unified dispatch logging and streaming dispatch configuration."""

import json
import subprocess
from pathlib import Path

from workflow.dispatch import (
    ClaudeAdapter,
    _recover_structured_output_from_conversation,
    _unwrap_structured_output_candidate,
)
from workflow.dispatch_log import DispatchLog, read_dispatch_artifacts, token_summary


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


class TestClaudeAdapterStructuredOutputParsing:
    """Claude adapter should prefer structured output over prose summaries."""

    def test_json_schema_mode_prefers_structured_output_when_result_has_summary(self) -> None:
        adapter = ClaudeAdapter()
        completed = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "num_turns": 61,
                    "result": "Plan generated successfully. Here's a summary...",
                    "structured_output": {
                        "epic_number": 146,
                        "schema_v": 1,
                        "goal": "test",
                    },
                }
            ),
            stderr="",
        )

        result = adapter.parse_result(completed)

        assert result.success is True
        assert result.turns == 61
        assert json.loads(result.output) == {
            "epic_number": 146,
            "schema_v": 1,
            "goal": "test",
        }
        assert result.structured_output == {
            "epic_number": 146,
            "schema_v": 1,
            "goal": "test",
        }

    def test_error_envelope_surfaces_json_diagnostics(self) -> None:
        adapter = ClaudeAdapter()
        completed = subprocess.CompletedProcess(
            args=["claude"],
            returncode=1,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "error_max_structured_output_retries",
                    "num_turns": 56,
                    "errors": ["Failed to provide valid structured output after 5 attempts"],
                }
            ),
            stderr="",
        )

        result = adapter.parse_result(completed)

        assert result.success is False
        assert result.turns == 56
        assert json.loads(result.output)["subtype"] == "error_max_structured_output_retries"


class TestStructuredOutputRecovery:
    def test_unwrap_structured_output_candidate_handles_result_wrapper(self) -> None:
        wrapped = {"result": {"schema_v": 1, "epic_number": 146, "goal": "test"}}

        assert _unwrap_structured_output_candidate(wrapped) == {
            "schema_v": 1,
            "epic_number": 146,
            "goal": "test",
        }

    def test_unwrap_structured_output_candidate_handles_schema_string_with_embedded_plan(
        self,
    ) -> None:
        malformed = {
            "$schema": json.dumps({"title": "Plan", "type": "object"})
            + json.dumps({"schema_v": 1, "epic_number": 146, "goal": "test"})
        }

        assert _unwrap_structured_output_candidate(malformed) == {
            "schema_v": 1,
            "epic_number": 146,
            "goal": "test",
        }

    def test_recover_structured_output_from_conversation_unwraps_singleton_wrapper(
        self, tmp_path
    ) -> None:
        conversation_log = tmp_path / "conversation.jsonl"
        conversation_log.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "seq": 1,
                            "payload": {
                                "type": "assistant",
                                "message": {
                                    "content": [
                                        {
                                            "type": "tool_use",
                                            "name": "StructuredOutput",
                                            "input": {
                                                "result": {
                                                    "schema_v": 1,
                                                    "epic_number": 146,
                                                    "goal": "test",
                                                }
                                            },
                                        }
                                    ]
                                },
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "seq": 2,
                            "payload": {
                                "type": "result",
                                "subtype": "error_max_structured_output_retries",
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        recovered = _recover_structured_output_from_conversation(conversation_log)

        assert recovered == {"schema_v": 1, "epic_number": 146, "goal": "test"}

    def test_recover_structured_output_from_conversation_extracts_embedded_plan_from_schema_string(
        self, tmp_path
    ) -> None:
        conversation_log = tmp_path / "conversation.jsonl"
        conversation_log.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "seq": 1,
                            "payload": {
                                "type": "assistant",
                                "message": {
                                    "content": [
                                        {
                                            "type": "tool_use",
                                            "name": "StructuredOutput",
                                            "input": {
                                                "$schema": json.dumps(
                                                    {"title": "Plan", "type": "object"}
                                                )
                                                + json.dumps(
                                                    {
                                                        "schema_v": 1,
                                                        "epic_number": 146,
                                                        "goal": "test",
                                                    }
                                                )
                                            },
                                        }
                                    ]
                                },
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "seq": 2,
                            "payload": {
                                "type": "result",
                                "subtype": "error_max_structured_output_retries",
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        recovered = _recover_structured_output_from_conversation(conversation_log)

        assert recovered == {"schema_v": 1, "epic_number": 146, "goal": "test"}


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
        assert Path(entries[1]["response_file"]).name == f"{dispatch.dispatch_id}-response.txt"

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

    def test_read_dispatch_artifacts_returns_typed_entries(self, tmp_path) -> None:
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
            turns=2,
            duration_ms=800,
        )

        entries = read_dispatch_artifacts(epic_dir)

        assert [entry.status for entry in entries] == ["started", "completed"]
        assert entries[0].dispatch_id == entries[1].dispatch_id
        assert entries[1].response_tokens is not None
