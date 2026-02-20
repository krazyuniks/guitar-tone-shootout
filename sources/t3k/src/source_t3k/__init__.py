"""GTS T3K Source Adapter.

Syncs gear data from Tone3000 API to t3k_* tables in gts_core.
Publishes sync records via pgmq for worker consumption.
"""

__version__ = "0.1.0"
