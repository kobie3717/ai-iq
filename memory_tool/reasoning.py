"""ReasoningBank-style retrieval boost for memories linked to confirmed predictions.

This module implements retrieval boosting based on prediction outcomes:
- Memories that led to confirmed predictions get a ranking boost (1.5x per link)
- Memories that led to refuted predictions get a penalty (0.67x per link)
- Boost is capped at 2.0x to prevent runaway compounding
- Links discovered via:
  1. Direct prediction.memory_id
  2. Memory relations table
  3. derived_from field (JSON array)
  4. citations field (comma-separated IDs)
  5. reasoning field (comma-separated IDs)

This grounds memory retrieval against verifiable outcomes, addressing the
"reinforced lies" problem by prioritizing reasoning trajectories that actually worked.

Inspired by ruvnet/ruflo ReasoningBank pattern.
"""

import sqlite3
import json
import re
from typing import Dict, List, Tuple, Set
from .database import get_db
from .config import get_logger, REASONING_BOOST_BASE, REASONING_BOOST_CAP

logger = get_logger(__name__)


def _extract_memory_ids_from_field(field_value: str) -> Set[int]:
    """Extract memory IDs from a comma-separated or JSON array field.

    Args:
        field_value: String that might contain memory IDs (e.g., "1,2,3" or "[1,2,3]")

    Returns:
        Set of memory IDs
    """
    if not field_value:
        return set()

    ids = set()

    # Try JSON array first
    if field_value.strip().startswith('['):
        try:
            parsed = json.loads(field_value)
            if isinstance(parsed, list):
                for item in parsed:
                    try:
                        ids.add(int(item))
                    except (ValueError, TypeError):
                        pass
            return ids
        except json.JSONDecodeError:
            pass

    # Fall back to comma-separated
    for part in field_value.split(','):
        part = part.strip()
        # Extract numbers only (ignore text like "memory #5" -> 5)
        match = re.search(r'\d+', part)
        if match:
            try:
                ids.add(int(match.group()))
            except ValueError:
                pass

    return ids


def _find_prediction_memories(memory_id: int, conn: sqlite3.Connection) -> Tuple[Set[int], Set[int]]:
    """Find all memories that contain confirmed or refuted predictions linked to this memory.

    Checks:
    1. Direct prediction.memory_id link
    2. Memory relations (linked via memory_relations table)
    3. derived_from field (JSON array of source memory IDs)
    4. citations field (comma-separated memory IDs)
    5. reasoning field (comma-separated memory IDs)

    Args:
        memory_id: Memory ID to search for
        conn: Database connection

    Returns:
        Tuple of (confirmed_prediction_ids, refuted_prediction_ids)
    """
    confirmed_preds = set()
    refuted_preds = set()

    # 1. Direct prediction.memory_id link (original implementation)
    direct_preds = conn.execute("""
        SELECT id, status FROM predictions
        WHERE memory_id = ? AND status IN ('confirmed', 'refuted')
    """, (memory_id,)).fetchall()

    for pred in direct_preds:
        if pred['status'] == 'confirmed':
            confirmed_preds.add(pred['id'])
        elif pred['status'] == 'refuted':
            refuted_preds.add(pred['id'])

    # 2. Find all memories that link to this memory via relations, derived_from, citations, or reasoning
    # and check if those memories have predictions

    # 2a. Memory relations: memories that reference this memory
    related_mems = conn.execute("""
        SELECT DISTINCT source_id FROM memory_relations
        WHERE target_id = ?
    """, (memory_id,)).fetchall()

    related_mem_ids = {row['source_id'] for row in related_mems}

    # 2b. Memories that cite this memory in derived_from, citations, or reasoning
    citing_mems = conn.execute("""
        SELECT id, derived_from, citations, reasoning FROM memories
        WHERE active = 1
        AND (
            derived_from IS NOT NULL
            OR citations IS NOT NULL
            OR reasoning IS NOT NULL
        )
    """).fetchall()

    for mem in citing_mems:
        # Check if this memory cites our target memory
        cited_ids = set()

        if mem['derived_from']:
            cited_ids.update(_extract_memory_ids_from_field(mem['derived_from']))
        if mem['citations']:
            cited_ids.update(_extract_memory_ids_from_field(mem['citations']))
        if mem['reasoning']:
            cited_ids.update(_extract_memory_ids_from_field(mem['reasoning']))

        if memory_id in cited_ids:
            related_mem_ids.add(mem['id'])

    # Now check if any of these related memories have predictions
    if related_mem_ids:
        placeholders = ','.join('?' * len(related_mem_ids))
        related_preds = conn.execute(f"""
            SELECT id, status FROM predictions
            WHERE memory_id IN ({placeholders})
            AND status IN ('confirmed', 'refuted')
        """, list(related_mem_ids)).fetchall()

        for pred in related_preds:
            if pred['status'] == 'confirmed':
                confirmed_preds.add(pred['id'])
            elif pred['status'] == 'refuted':
                refuted_preds.add(pred['id'])

    return confirmed_preds, refuted_preds


def compute_reasoning_boost(memory_id: int, conn: sqlite3.Connection = None) -> float:
    """Compute reasoning boost factor for a memory based on linked predictions.

    Args:
        memory_id: ID of the memory to compute boost for
        conn: Database connection (will create one if not provided)

    Returns:
        Boost factor between 0.3 and REASONING_BOOST_CAP:
        - 1.0 = neutral (no linked predictions)
        - >1.0 = memory led to confirmed predictions
        - <1.0 = memory led to refuted predictions

    Formula:
        For each confirmed prediction link: multiply by REASONING_BOOST_BASE (1.3x)
        For each refuted prediction link: divide by 1.3x
        Cap at REASONING_BOOST_CAP (1.8x) to prevent runaway compounding
    """
    should_close = conn is None
    if conn is None:
        conn = get_db()

    try:
        confirmed_preds, refuted_preds = _find_prediction_memories(memory_id, conn)

        confirmed_count = len(confirmed_preds)
        refuted_count = len(refuted_preds)

        # Start at 1.0 (neutral)
        boost = 1.0

        # Apply confirmed boosts (multiplicative)
        # Use power for efficiency: boost = REASONING_BOOST_BASE ^ confirmed_count
        if confirmed_count > 0:
            boost *= (REASONING_BOOST_BASE ** confirmed_count)

        # Apply refuted penalties (divide by boost factor)
        # Use power for efficiency: boost = boost / (REASONING_BOOST_BASE ^ refuted_count)
        if refuted_count > 0:
            boost /= (REASONING_BOOST_BASE ** refuted_count)

        # Clamp to reasonable range [0.3, REASONING_BOOST_CAP]
        boost = max(0.3, min(REASONING_BOOST_CAP, boost))

        return boost

    finally:
        if should_close:
            conn.close()


def get_memory_reasoning_stats(memory_id: int) -> Dict[str, int]:
    """Get prediction statistics for a memory.

    Args:
        memory_id: ID of the memory

    Returns:
        Dictionary with keys: confirmed, refuted, open, total
    """
    conn = get_db()

    stats = {
        'confirmed': 0,
        'refuted': 0,
        'open': 0,
        'total': 0
    }

    # Get counts by status
    rows = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM predictions
        WHERE memory_id = ?
        GROUP BY status
    """, (memory_id,)).fetchall()

    for row in rows:
        status = row['status']
        count = row['count']
        stats['total'] += count
        if status in stats:
            stats[status] = count

    conn.close()
    return stats


def list_memories_by_reasoning() -> List[Tuple[int, str, int, int, float]]:
    """List all memories ranked by reasoning boost (highest first).

    Returns:
        List of tuples: (memory_id, content_preview, confirmed_count, refuted_count, boost_factor)
        Sorted by boost factor descending.
    """
    conn = get_db()

    # Get all memories with prediction links
    memories = conn.execute("""
        SELECT DISTINCT m.id, m.content
        FROM memories m
        WHERE m.active = 1
        AND m.id IN (SELECT DISTINCT memory_id FROM predictions WHERE memory_id IS NOT NULL)
        ORDER BY m.id
    """).fetchall()

    results = []
    for mem in memories:
        mem_id = mem['id']
        content = mem['content']

        # Get stats
        stats = get_memory_reasoning_stats(mem_id)
        confirmed = stats['confirmed']
        refuted = stats['refuted']

        # Compute boost
        boost = compute_reasoning_boost(mem_id, conn)

        # Preview: first 80 chars
        preview = content[:80] + ('...' if len(content) > 80 else '')

        results.append((mem_id, preview, confirmed, refuted, boost))

    conn.close()

    # Sort by boost descending
    results.sort(key=lambda x: -x[4])

    return results


def apply_reasoning_boost_to_scores(scores: Dict[int, float], conn: sqlite3.Connection = None) -> None:
    """Apply reasoning boost to a dictionary of memory scores (in-place).

    This is designed to be called from search_memories() after RRF scoring.

    Args:
        scores: Dictionary mapping memory_id -> score (modified in-place)
        conn: Database connection (will create one if not provided)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db()

    try:
        for mem_id in scores:
            boost = compute_reasoning_boost(mem_id, conn)
            if boost != 1.0:
                scores[mem_id] *= boost
                logger.debug(f"Applied reasoning boost {boost:.2f}x to memory #{mem_id}")
    finally:
        if should_close:
            conn.close()
