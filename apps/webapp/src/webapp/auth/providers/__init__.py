"""OAuth provider implementations.

This package contains provider-specific OAuth implementations for:
- T3K (Tone3000) OAuth provider
"""

from webapp.auth.providers.t3k import T3KProvider

__all__ = ["T3KProvider"]
