"""GTS Worker.

TaskIQ background jobs and pgmq message consumer.
Bridges gts_core and gts_t3k_source databases.
"""

__version__ = "0.1.0"

from worker.main import broker

__all__ = ["broker"]
