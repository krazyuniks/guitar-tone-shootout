"""Re-export SignalChainBlock for backward compatibility.

This module exists to support imports like:
    from webapp.adapters.persistence.models.signal_chain_block import SignalChainBlock

The actual implementation is in signal_chain.py where SignalChainBlock
is defined alongside SignalChain.
"""

from .signal_chain import SignalChainBlock

__all__ = ["SignalChainBlock"]
