"""Per-dispatch conversation logger — lossless agent transcript capture.

Wraps each line from an agent's --output-format stream-json stdout in a thin
envelope and writes it to a JSONL file. Non-JSON lines (startup messages,
progress indicators) are captured as anomaly events with a seq number to
preserve full audit trail integrity.

Design: passthrough, not normalised. The payload is the raw event from the
provider — no information is dropped during capture.

Reference: wiki/Epic-Workflow.md, Conversation Logging section.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class ConversationLogger:
    """Captures streaming agent output to a conversation JSONL file.

    Each line from the agent's stdout is wrapped in an envelope:
    {"ts": "ISO 8601", "provider": "claude", "model": "opus", "seq": 1, "payload": {...}}

    Non-JSON lines are logged as anomaly events:
    {"ts": "ISO 8601", "provider": "claude", "model": "opus", "seq": 2, "anomaly": true, "raw": "..."}
    """

    def __init__(
        self,
        log_path: Path,
        provider: str,
        model: str,
    ) -> None:
        self._log_path = log_path
        self._provider = provider
        self._model = model
        self._seq = 0
        self._file = None

    def open(self) -> None:
        """Open the log file for writing."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._log_path.open("a", encoding="utf-8")

    def close(self) -> None:
        """Close the log file."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> ConversationLogger:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def process_line(self, raw_line: str) -> None:
        """Process one line of agent stdout.

        JSON lines are wrapped in an envelope with the native payload.
        Non-JSON lines are wrapped as anomaly events.
        """
        line = raw_line.rstrip("\n\r")
        if not line:
            return

        self._seq += 1
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        try:
            payload = json.loads(line)
            envelope = {
                "ts": ts,
                "provider": self._provider,
                "model": self._model,
                "seq": self._seq,
                "payload": payload,
            }
        except json.JSONDecodeError:
            envelope = {
                "ts": ts,
                "provider": self._provider,
                "model": self._model,
                "seq": self._seq,
                "anomaly": True,
                "raw": line[:500],
            }

        self._write_envelope(envelope)

    def _write_envelope(self, envelope: dict) -> None:
        """Write a single envelope to the log file."""
        if self._file is None:
            return
        self._file.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        self._file.flush()

    @property
    def seq(self) -> int:
        """Current sequence number."""
        return self._seq

    @property
    def log_path(self) -> Path:
        """Path to the conversation log file."""
        return self._log_path
