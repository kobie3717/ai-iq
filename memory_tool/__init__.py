"""
AI-IQ: Persistent memory system for AI agents.

SQLite-backed with FTS5, hybrid search (keyword + semantic), knowledge graph,
belief tracking with confidence scoring, dream consolidation, and self-learning.

CLI Usage:
    memory-tool add learning "Docker needs network_mode: host for Redis"
    memory-tool search "docker networking"

Python API Usage:
    from ai_iq import Memory

    memory = Memory()
    memory.add("User likes Bitcoin", tags=["crypto", "preference"])
    results = memory.search("bitcoin")
"""

__version__ = "5.7.0"

# Export the main API class for "from ai_iq import Memory"
from .api import Memory

__all__ = ["Memory", "__version__"]
