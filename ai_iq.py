"""AI-IQ Python API - Compatibility wrapper.

This module provides a clean import path: `from ai_iq import Memory`
while maintaining backward compatibility with the memory_tool CLI.
"""

from memory_tool import Memory, __version__

__all__ = ["Memory", "__version__"]
