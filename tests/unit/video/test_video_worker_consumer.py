"""Regression tests for video worker consumer startup imports."""

from video_worker.consumer import RenderVideoConsumer


class _SessionStub:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def expunge_all(self) -> None:
        return None


def test_render_video_consumer_uses_shootout_queue() -> None:
    """RenderVideoConsumer imports and consumes the orchestration queue."""
    consumer = RenderVideoConsumer(_SessionStub())

    assert consumer.queue_name == "shootout_commands"
    assert consumer.dead_letter_queue == "dead_letter"
