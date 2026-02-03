"""GTS Worker - TaskIQ broker and job definitions.

This module provides the TaskIQ broker configuration and job handlers.
"""

from taskiq import InMemoryBroker

# Broker instance - will be replaced with Redis broker in production
broker = InMemoryBroker()


@broker.task
async def example_task(message: str) -> str:
    """Example task for testing.

    Args:
        message: A test message

    Returns:
        Processed message
    """
    return f"Processed: {message}"
