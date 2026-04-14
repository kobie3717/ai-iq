"""Context Window Budgeting for memory retrieval (Upgrade 5)."""

import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from .config import get_logger
from .database import get_db

logger = get_logger(__name__)


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estimate token count from text.

    Args:
        text: Text to estimate
        chars_per_token: Average characters per token (default 4.0 for English)

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return max(1, int(len(text) / chars_per_token))


def memory_to_text(memory: Dict[str, Any], include_metadata: bool = True) -> str:
    """
    Convert memory to text for token counting.

    Args:
        memory: Memory dict
        include_metadata: Include category, tags, project in output

    Returns:
        Formatted text representation
    """
    parts = []

    if include_metadata:
        if memory.get('category'):
            parts.append(f"[{memory['category']}]")
        if memory.get('project'):
            parts.append(f"({memory['project']})")

    parts.append(memory.get('content', ''))

    if include_metadata and memory.get('tags'):
        parts.append(f"#{memory['tags']}")

    return " ".join(parts)


def retrieve_with_budget(
    query: str,
    token_budget: int = 2000,
    chars_per_token: float = 4.0,
    min_importance: float = 0.0,
    search_mode: str = "hybrid",
    project: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    include_metadata: bool = True
) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
    """
    Search memories and return as many as fit within token_budget.

    Prioritizes by importance score descending, then truncates to fit budget.

    Args:
        query: Search query
        token_budget: Maximum tokens to return (default 2000)
        chars_per_token: Characters per token estimate (default 4.0)
        min_importance: Filter out memories below this importance score
        search_mode: "hybrid", "semantic", or "keyword"
        project: Filter by project
        category: Filter by category
        tags: Filter by tags
        include_metadata: Include category/tags/project in token count

    Returns:
        Tuple of (memories, tokens_used, stats_dict)
    """
    # Import here to avoid circular dependency
    from .memory_ops import search_memories

    # Search for memories
    all_results = search_memories(
        query=query,
        mode=search_mode,
        project=project,
        category=category,
        tags=tags,
        limit=100  # Get more candidates
    )

    if not all_results:
        return [], 0, {
            'total_candidates': 0,
            'filtered_by_importance': 0,
            'selected': 0,
            'budget_used': 0,
            'budget_limit': token_budget,
            'budget_pct': 0.0
        }

    # Convert to list of dicts if needed
    memories = []
    for result in all_results:
        if isinstance(result, sqlite3.Row):
            memories.append(dict(result))
        elif isinstance(result, dict):
            memories.append(result)

    total_candidates = len(memories)

    # Filter by minimum importance
    if min_importance > 0:
        memories = [m for m in memories if m.get('imp_score', 0) >= min_importance]

    filtered_count = total_candidates - len(memories)

    # Sort by importance score descending
    memories.sort(key=lambda m: m.get('imp_score', 0), reverse=True)

    # Fit within budget
    selected = []
    tokens_used = 0

    for memory in memories:
        text = memory_to_text(memory, include_metadata=include_metadata)
        mem_tokens = estimate_tokens(text, chars_per_token)

        if tokens_used + mem_tokens <= token_budget:
            selected.append(memory)
            tokens_used += mem_tokens
        else:
            # Budget exceeded, stop
            break

    budget_pct = (tokens_used / token_budget * 100) if token_budget > 0 else 0.0

    stats = {
        'total_candidates': total_candidates,
        'filtered_by_importance': filtered_count,
        'selected': len(selected),
        'budget_used': tokens_used,
        'budget_limit': token_budget,
        'budget_pct': round(budget_pct, 1)
    }

    return selected, tokens_used, stats


def format_memories_for_context(
    memories: List[Dict[str, Any]],
    include_metadata: bool = True,
    separator: str = "\n\n---\n\n"
) -> str:
    """
    Format memories as text for injection into prompt context.

    Args:
        memories: List of memory dicts
        include_metadata: Include category/tags/project
        separator: Separator between memories

    Returns:
        Formatted text
    """
    formatted = []

    for i, memory in enumerate(memories, 1):
        parts = []

        if include_metadata:
            meta = []
            if memory.get('id'):
                meta.append(f"ID: {memory['id']}")
            if memory.get('category'):
                meta.append(f"Category: {memory['category']}")
            if memory.get('project'):
                meta.append(f"Project: {memory['project']}")
            if memory.get('imp_score'):
                meta.append(f"Importance: {memory['imp_score']:.1f}")

            if meta:
                parts.append(f"[{' | '.join(meta)}]")

        parts.append(memory.get('content', ''))

        if include_metadata and memory.get('tags'):
            parts.append(f"Tags: {memory['tags']}")

        formatted.append("\n".join(parts))

    return separator.join(formatted)


def budget_stats() -> Dict[str, Any]:
    """
    Get statistics about memory token usage.

    Returns dict with total memories, total tokens, avg tokens per memory, etc.
    """
    conn = get_db()

    total_memories = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE active = 1"
    ).fetchone()[0]

    if total_memories == 0:
        conn.close()
        return {
            'total_memories': 0,
            'total_tokens': 0,
            'avg_tokens': 0,
            'max_tokens': 0,
            'min_tokens': 0
        }

    # Get all active memories
    memories = conn.execute(
        "SELECT content, category, project, tags FROM memories WHERE active = 1"
    ).fetchall()

    conn.close()

    # Calculate token counts
    token_counts = []
    for mem in memories:
        text = memory_to_text(dict(mem), include_metadata=True)
        tokens = estimate_tokens(text)
        token_counts.append(tokens)

    total_tokens = sum(token_counts)
    avg_tokens = total_tokens / len(token_counts) if token_counts else 0
    max_tokens = max(token_counts) if token_counts else 0
    min_tokens = min(token_counts) if token_counts else 0

    return {
        'total_memories': total_memories,
        'total_tokens': total_tokens,
        'avg_tokens': round(avg_tokens, 1),
        'max_tokens': max_tokens,
        'min_tokens': min_tokens
    }
