"""Clean Python API for AI-IQ memory system.

This module provides a simple, high-level Python API for using AI-IQ as a library
rather than via CLI. All methods are thread-safe via SQLite WAL mode.

Example:
    >>> from ai_iq import Memory
    >>>
    >>> memory = Memory()  # Uses ./memories.db
    >>> memory.add("User likes Bitcoin", tags=["crypto", "preference"])
    >>> results = memory.search("bitcoin")
    >>> print(results[0]["content"])
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import sqlite3

from .database import init_db, get_db
from .memory_ops import (
    add_memory as _add_memory,
    search_memories as _search_memories,
    get_memory as _get_memory,
    update_memory as _update_memory,
    delete_memory as _delete_memory,
    list_memories as _list_memories,
)
from .config import DB_PATH as DEFAULT_DB_PATH


class Memory:
    """AI-IQ Memory system API.

    Provides a clean Python interface to the AI-IQ persistent memory system.
    All operations are thread-safe via SQLite WAL mode with busy timeout.

    Args:
        db_path: Path to SQLite database file. Defaults to ./memories.db
                If path doesn't exist, database will be initialized automatically.

    Example:
        >>> memory = Memory("my_memories.db")
        >>> mem_id = memory.add("Important fact", tags=["work"])
        >>> results = memory.search("important")
        >>> memory.update(mem_id, "Very important fact")
        >>> memory.delete(mem_id)
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize memory system with optional custom database path.

        Args:
            db_path: Path to SQLite database. If None, uses ./memories.db
        """
        if db_path is not None:
            # Override the default DB_PATH temporarily
            from . import config
            self._db_path = Path(db_path).resolve()
            # Monkey-patch the global DB_PATH for this instance
            # This is safe because each get_db() call uses the current value
            config.DB_PATH = self._db_path
        else:
            self._db_path = DEFAULT_DB_PATH

        # Initialize database if it doesn't exist
        init_db()

    def add(
        self,
        content: str,
        category: str = "general",
        tags: Optional[str] = None,
        project: Optional[str] = None,
        priority: int = 0,
        related_to: Optional[int] = None,
        expires_at: Optional[str] = None,
    ) -> Optional[int]:
        """Add a new memory.

        Args:
            content: The memory content (required)
            category: Category type. One of: project, decision, preference, error,
                     learning, pending, architecture, workflow, contact, general
            tags: Comma-separated tags (e.g., "crypto,finance") or list of tags
            project: Project name to associate this memory with
            priority: Priority level 0-10 (higher = more important)
            related_to: ID of related memory to link to
            expires_at: Expiry date in YYYY-MM-DD format for temporary memories

        Returns:
            Memory ID if created, None if duplicate was blocked

        Example:
            >>> mem_id = memory.add(
            ...     "Use Redis for session storage",
            ...     category="decision",
            ...     tags="redis,caching",
            ...     project="MyApp",
            ...     priority=8
            ... )
        """
        # Convert list to comma-separated string if needed
        if isinstance(tags, list):
            tags = ",".join(tags)

        return _add_memory(
            category=category,
            content=content,
            tags=tags or "",
            project=project,
            priority=priority,
            related_to=related_to,
            expires_at=expires_at,
        )

    def search(
        self,
        query: str,
        mode: str = "hybrid",
    ) -> List[Dict[str, Any]]:
        """Search memories with hybrid keyword + semantic search.

        Args:
            query: Search query string
            mode: Search mode - "hybrid" (default), "keyword", or "semantic"

        Returns:
            List of memory dictionaries with keys: id, content, category, tags,
            project, priority, created_at, updated_at, confidence, etc.

        Example:
            >>> results = memory.search("redis caching")
            >>> for r in results:
            ...     print(f"#{r['id']}: {r['content']}")
        """
        rows, _search_id = _search_memories(query, mode=mode)
        # Convert sqlite3.Row objects to dictionaries
        return [dict(row) for row in rows]

    def get(self, mem_id: int) -> Optional[Dict[str, Any]]:
        """Get full details for a single memory by ID.

        Args:
            mem_id: Memory ID

        Returns:
            Dictionary with all memory fields, or None if not found

        Example:
            >>> mem = memory.get(42)
            >>> if mem:
            ...     print(mem["content"])
        """
        row = _get_memory(mem_id)
        return dict(row) if row else None

    def update(self, mem_id: int, content: str) -> None:
        """Update a memory's content.

        Auto-updates tags, revision count, and re-generates embeddings.

        Args:
            mem_id: Memory ID to update
            content: New content

        Example:
            >>> memory.update(42, "Updated content here")
        """
        _update_memory(mem_id, content)

    def delete(self, mem_id: int) -> None:
        """Soft-delete a memory (marks as inactive, recoverable).

        Args:
            mem_id: Memory ID to delete

        Example:
            >>> memory.delete(42)
        """
        _delete_memory(mem_id)

    def list(
        self,
        category: Optional[str] = None,
        project: Optional[str] = None,
        tag: Optional[str] = None,
        stale_only: bool = False,
        expired_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List memories with optional filters.

        Args:
            category: Filter by category
            project: Filter by project name
            tag: Filter by tag (partial match)
            stale_only: Only show stale memories
            expired_only: Only show expired memories

        Returns:
            List of memory dictionaries

        Example:
            >>> # Get all memories for a project
            >>> mems = memory.list(project="MyApp")
            >>>
            >>> # Get all pending items
            >>> todos = memory.list(category="pending")
            >>>
            >>> # Get stale memories that need review
            >>> stale = memory.list(stale_only=True)
        """
        rows = _list_memories(
            category=category,
            project=project,
            tag=tag,
            stale_only=stale_only,
            expired_only=expired_only,
        )
        return [dict(row) for row in rows]

    def stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with memory counts, vector counts, etc.

        Example:
            >>> stats = memory.stats()
            >>> print(f"Total memories: {stats['total']}")
            >>> print(f"Active memories: {stats['active']}")
        """
        conn = get_db()

        # Get basic counts
        total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) as c FROM memories WHERE active = 1").fetchone()["c"]

        # Get category breakdown
        category_counts = {}
        for row in conn.execute("SELECT category, COUNT(*) as c FROM memories WHERE active = 1 GROUP BY category"):
            category_counts[row["category"] or "unknown"] = row["c"]

        # Get vector count if available
        vector_count = 0
        try:
            vector_count = conn.execute("SELECT COUNT(*) as c FROM memory_vec").fetchone()["c"]
        except sqlite3.OperationalError:
            pass  # Vec table doesn't exist

        conn.close()

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "categories": category_counts,
            "vectors": vector_count,
        }
