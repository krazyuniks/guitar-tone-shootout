"""GTS T3K Source Adapter.

Syncs gear data from Tone3000 API to gts_t3k_source database.
Publishes sync records via pgmq for worker consumption.
"""

__version__ = "0.1.0"
