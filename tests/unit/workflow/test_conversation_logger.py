"""Tests for conversation logger."""

import json

from workflow.conversation_logger import ConversationLogger


class TestConversationLogger:
    """Test ConversationLogger envelope wrapping."""

    def test_json_line_wrapped_in_envelope(self, tmp_path):
        log_path = tmp_path / "conv.jsonl"
        with ConversationLogger(log_path, "claude", "opus") as cl:
            cl.process_line('{"type": "result", "text": "hello"}')

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        envelope = json.loads(lines[0])
        assert envelope["provider"] == "claude"
        assert envelope["model"] == "opus"
        assert envelope["seq"] == 1
        assert envelope["payload"]["type"] == "result"
        assert "anomaly" not in envelope

    def test_non_json_line_logged_as_anomaly(self, tmp_path):
        log_path = tmp_path / "conv.jsonl"
        with ConversationLogger(log_path, "claude", "opus") as cl:
            cl.process_line("Starting up...")

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        envelope = json.loads(lines[0])
        assert envelope["anomaly"] is True
        assert envelope["raw"] == "Starting up..."
        assert envelope["seq"] == 1

    def test_seq_increments(self, tmp_path):
        log_path = tmp_path / "conv.jsonl"
        with ConversationLogger(log_path, "codex", "gpt-5.3-codex") as cl:
            cl.process_line('{"event": 1}')
            cl.process_line("not json")
            cl.process_line('{"event": 2}')

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        seqs = [json.loads(line)["seq"] for line in lines]
        assert seqs == [1, 2, 3]

    def test_empty_lines_skipped(self, tmp_path):
        log_path = tmp_path / "conv.jsonl"
        with ConversationLogger(log_path, "claude", "opus") as cl:
            cl.process_line("")
            cl.process_line("\n")
            cl.process_line('{"event": 1}')

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_long_raw_line_truncated(self, tmp_path):
        log_path = tmp_path / "conv.jsonl"
        long_line = "x" * 1000
        with ConversationLogger(log_path, "claude", "opus") as cl:
            cl.process_line(long_line)

        envelope = json.loads(log_path.read_text().strip())
        assert envelope["anomaly"] is True
        assert len(envelope["raw"]) == 500

    def test_context_manager_creates_directory(self, tmp_path):
        log_path = tmp_path / "nested" / "dir" / "conv.jsonl"
        with ConversationLogger(log_path, "claude", "opus") as cl:
            cl.process_line('{"test": true}')

        assert log_path.exists()
