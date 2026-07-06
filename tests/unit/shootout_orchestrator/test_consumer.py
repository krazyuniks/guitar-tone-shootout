"""Regression tests for shootout orchestrator consumer startup imports."""

from shootout_orchestrator.consumer import StartShootoutConsumer


class _SessionStub:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def expunge_all(self) -> None:
        return None


def test_start_shootout_consumer_uses_shootout_queue() -> None:
    """StartShootoutConsumer imports and consumes the orchestration queue."""
    consumer = StartShootoutConsumer(_SessionStub())

    assert consumer.queue_name == "shootout_commands"
    assert consumer.dead_letter_queue == "dead_letter"
