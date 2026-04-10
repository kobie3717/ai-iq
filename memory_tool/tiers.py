"""Memory tier management for episodic/semantic/working memory model."""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import get_logger

logger = get_logger(__name__)


def classify_tier(memory_row: dict) -> str:
    """Auto-classify tier based on category, priority, tags, and age.

    Tier classification rules:
    - working: ephemeral session data (pending, error, expires within 24h)
    - episodic: recent events and learnings (default for most memories)
    - semantic: proven long-term knowledge (preference, architecture with proof_count >= 3)

    Args:
        memory_row: dict with keys: category, priority, tags, proof_count, expires_at, access_count

    Returns:
        Tier name: 'working', 'episodic', or 'semantic'
    """
    category = memory_row.get('category', 'learning')
    priority = memory_row.get('priority', 0)
    tags = memory_row.get('tags', '')
    proof_count = memory_row.get('proof_count', 1)
    expires_at = memory_row.get('expires_at')
    access_count = memory_row.get('access_count', 0)

    # Working tier: temporary/ephemeral memories
    if category in ('pending', 'error'):
        return 'working'

    # Check for expiry within 24h
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
            hours_until_expiry = (exp_dt - datetime.now()).total_seconds() / 3600
            if 0 < hours_until_expiry <= 24:
                return 'working'
        except (ValueError, AttributeError):
            pass

    # Semantic tier: proven long-term knowledge
    # High-confidence preferences and architectural decisions
    if category in ('preference', 'architecture') and proof_count >= 3:
        return 'semantic'

    # High access count indicates importance
    if access_count >= 5 and proof_count >= 3:
        return 'semantic'

    # Default: episodic (recent events, learnings, decisions)
    return 'episodic'


def promote_tier_pass(conn: sqlite3.Connection) -> int:
    """Promote memories from episodic to semantic based on proof and access.

    Promotion criteria:
    - proof_count >= 3 (consolidated from multiple sources)
    - access_count >= 5 (frequently referenced)
    - category in ('preference', 'architecture', 'learning', 'decision')

    Args:
        conn: Database connection

    Returns:
        Number of memories promoted
    """
    # Find episodic memories that qualify for semantic promotion
    candidates = conn.execute("""
        SELECT id, category, proof_count, access_count
        FROM memories
        WHERE active = 1
        AND tier = 'episodic'
        AND proof_count >= 3
        AND access_count >= 5
        AND category IN ('preference', 'architecture', 'learning', 'decision')
    """).fetchall()

    promoted = 0
    for mem in candidates:
        conn.execute("UPDATE memories SET tier = 'semantic' WHERE id = ?", (mem['id'],))
        promoted += 1
        logger.debug(f"Promoted #{mem['id']} to semantic (proof={mem['proof_count']}, access={mem['access_count']})")

    conn.commit()
    return promoted


def demote_tier_pass(conn: sqlite3.Connection) -> int:
    """Demote memories from semantic to episodic if they become stale with low access.

    Demotion criteria:
    - stale = 1 (flagged by decay process)
    - access_count < 2 (rarely used)
    - NOT in critical categories (preference stays semantic)

    Args:
        conn: Database connection

    Returns:
        Number of memories demoted
    """
    # Find semantic memories that should be demoted
    # Keep preferences semantic even if stale (user preferences don't change easily)
    candidates = conn.execute("""
        SELECT id, category, access_count, stale
        FROM memories
        WHERE active = 1
        AND tier = 'semantic'
        AND stale = 1
        AND access_count < 2
        AND category NOT IN ('preference')
    """).fetchall()

    demoted = 0
    for mem in candidates:
        conn.execute("UPDATE memories SET tier = 'episodic' WHERE id = ?", (mem['id'],))
        demoted += 1
        logger.debug(f"Demoted #{mem['id']} to episodic (stale, low access={mem['access_count']})")

    conn.commit()
    return demoted


def expire_working(conn: sqlite3.Connection, hours: int = 24) -> int:
    """Delete working tier memories older than specified hours.

    Working tier is ephemeral - memories should either:
    - Be promoted to episodic (if accessed/useful)
    - Expire after 24h (if never accessed)

    Args:
        conn: Database connection
        hours: Age threshold in hours (default 24)

    Returns:
        Number of memories deleted
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    # Find working memories older than cutoff that were never accessed
    candidates = conn.execute("""
        SELECT id, created_at, access_count
        FROM memories
        WHERE active = 1
        AND tier = 'working'
        AND created_at < ?
        AND (access_count = 0 OR access_count IS NULL)
    """, (cutoff_str,)).fetchall()

    expired = 0
    for mem in candidates:
        # Soft delete (set active = 0)
        conn.execute("UPDATE memories SET active = 0 WHERE id = ?", (mem['id'],))
        expired += 1
        logger.debug(f"Expired working memory #{mem['id']} (age > {hours}h, never accessed)")

    conn.commit()
    return expired


def tier_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """Get counts for each tier.

    Args:
        conn: Database connection

    Returns:
        Dict with keys: working, episodic, semantic, total
    """
    stats = conn.execute("""
        SELECT
            tier,
            COUNT(*) as count
        FROM memories
        WHERE active = 1
        GROUP BY tier
    """).fetchall()

    result = {
        'working': 0,
        'episodic': 0,
        'semantic': 0,
        'total': 0
    }

    for row in stats:
        tier = row['tier'] or 'episodic'  # Default to episodic if NULL
        result[tier] = row['count']
        result['total'] += row['count']

    return result


def promote_memory_to_tier(conn: sqlite3.Connection, mem_id: int, target_tier: str) -> None:
    """Manually promote a memory to a specific tier.

    Args:
        conn: Database connection
        mem_id: Memory ID to promote
        target_tier: Target tier ('working', 'episodic', 'semantic')

    Raises:
        ValueError: If target_tier is invalid
    """
    if target_tier not in ('working', 'episodic', 'semantic'):
        raise ValueError(f"Invalid tier: {target_tier}. Must be working, episodic, or semantic")

    # Get current tier
    current = conn.execute("SELECT tier FROM memories WHERE id = ?", (mem_id,)).fetchone()
    if not current:
        raise ValueError(f"Memory #{mem_id} not found")

    conn.execute("UPDATE memories SET tier = ? WHERE id = ?", (target_tier, mem_id))
    conn.commit()
    logger.info(f"Manually promoted #{mem_id} from {current['tier']} to {target_tier}")


def demote_memory_to_tier(conn: sqlite3.Connection, mem_id: int, target_tier: str) -> None:
    """Manually demote a memory to a specific tier.

    Args:
        conn: Database connection
        mem_id: Memory ID to demote
        target_tier: Target tier ('working', 'episodic', 'semantic')

    Raises:
        ValueError: If target_tier is invalid
    """
    if target_tier not in ('working', 'episodic', 'semantic'):
        raise ValueError(f"Invalid tier: {target_tier}. Must be working, episodic, or semantic")

    # Get current tier
    current = conn.execute("SELECT tier FROM memories WHERE id = ?", (mem_id,)).fetchone()
    if not current:
        raise ValueError(f"Memory #{mem_id} not found")

    conn.execute("UPDATE memories SET tier = ? WHERE id = ?", (target_tier, mem_id))
    conn.commit()
    logger.info(f"Manually demoted #{mem_id} from {current['tier']} to {target_tier}")
