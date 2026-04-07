"""Search feedback tracking and learning system."""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from .database import get_db

logger = logging.getLogger(__name__)


def log_search_feedback(search_id: int, used_ids: List[int]) -> None:
    """Mark which search results were actually used by the caller.

    Args:
        search_id: The search_log ID from the original search
        used_ids: List of memory IDs that were actually used from the search results
    """
    conn = get_db()

    # Get the search record
    row = conn.execute("SELECT result_ids FROM search_log WHERE id = ?", (search_id,)).fetchone()
    if not row or not row['result_ids']:
        conn.close()
        logger.warning(f"Search #{search_id} not found or has no results")
        return

    # Parse result_ids
    result_ids = [int(x) for x in row['result_ids'].split(',') if x]

    # Calculate hit rate
    used_count = len([uid for uid in used_ids if uid in result_ids])
    hit_rate = used_count / len(result_ids) if result_ids else 0.0

    # Store used_ids
    used_ids_str = ','.join(str(x) for x in used_ids)

    conn.execute("""
        UPDATE search_log SET used_ids = ?, hit_rate = ?
        WHERE id = ?
    """, (used_ids_str, hit_rate, search_id))

    # Boost access_count for used memories (they were helpful)
    if used_ids:
        placeholders = ','.join('?' * len(used_ids))
        conn.execute(f"""
            UPDATE memories
            SET access_count = access_count + 1,
                accessed_at = datetime('now')
            WHERE id IN ({placeholders})
        """, used_ids)

    # Slightly decrease priority for retrieved-but-unused memories (optional, gentle decay)
    unused_ids = [rid for rid in result_ids if rid not in used_ids]
    if unused_ids and len(unused_ids) < len(result_ids):  # Only if some were used
        placeholders = ','.join('?' * len(unused_ids))
        conn.execute(f"""
            UPDATE memories
            SET priority = MAX(0, priority - 1)
            WHERE id IN ({placeholders}) AND priority > 0
        """, unused_ids)

    conn.commit()
    conn.close()
    logger.info(f"Feedback logged for search #{search_id}: {used_count}/{len(result_ids)} hits ({hit_rate:.1%})")


def get_search_quality_stats() -> Dict[str, Any]:
    """Return search quality metrics.

    Returns:
        Dict with:
        - hit_rates: Overall hit rates (7d, 30d, all)
        - most_helpful: Top 10 memories with highest hit rate
        - least_helpful: Bottom 10 memories (retrieved often but rarely used)
        - search_patterns: Most common queries and their success rates
        - failing_queries: Queries with 0% hit rate
    """
    conn = get_db()
    now = datetime.now()

    stats = {}

    # Overall hit rates by time period
    try:
        # Last 7 days
        week_ago = (now - timedelta(days=7)).isoformat()
        row = conn.execute("""
            SELECT AVG(hit_rate) as avg_hit_rate, COUNT(*) as search_count
            FROM search_log
            WHERE created_at >= ? AND used_ids IS NOT NULL
        """, (week_ago,)).fetchone()
        stats['hit_rate_7d'] = {
            'rate': row['avg_hit_rate'] or 0.0,
            'searches': row['search_count'] or 0
        }

        # Last 30 days
        month_ago = (now - timedelta(days=30)).isoformat()
        row = conn.execute("""
            SELECT AVG(hit_rate) as avg_hit_rate, COUNT(*) as search_count
            FROM search_log
            WHERE created_at >= ? AND used_ids IS NOT NULL
        """, (month_ago,)).fetchone()
        stats['hit_rate_30d'] = {
            'rate': row['avg_hit_rate'] or 0.0,
            'searches': row['search_count'] or 0
        }

        # All time
        row = conn.execute("""
            SELECT AVG(hit_rate) as avg_hit_rate, COUNT(*) as search_count
            FROM search_log
            WHERE used_ids IS NOT NULL
        """).fetchone()
        stats['hit_rate_all'] = {
            'rate': row['avg_hit_rate'] or 0.0,
            'searches': row['search_count'] or 0
        }
    except sqlite3.OperationalError:
        # search_log table might not exist yet
        stats['hit_rate_7d'] = {'rate': 0.0, 'searches': 0}
        stats['hit_rate_30d'] = {'rate': 0.0, 'searches': 0}
        stats['hit_rate_all'] = {'rate': 0.0, 'searches': 0}

    # Most helpful memories (highest hit rate, min 5 retrievals)
    try:
        # Build a temp table of memory hit rates
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS memory_feedback AS
            SELECT
                m.id as mem_id,
                m.content,
                m.category,
                COUNT(*) as retrieve_count,
                SUM(CASE WHEN sl.used_ids LIKE '%' || m.id || '%' THEN 1 ELSE 0 END) as used_count
            FROM memories m
            JOIN (
                SELECT DISTINCT mem_id, search_id
                FROM (
                    -- Flatten search results
                    SELECT CAST(value AS INTEGER) as mem_id, sl.id as search_id
                    FROM search_log sl, json_each('["' || REPLACE(sl.result_ids, ',', '","') || '"]')
                    WHERE sl.result_ids IS NOT NULL
                )
            ) results ON results.mem_id = m.id
            JOIN search_log sl ON sl.id = results.search_id
            WHERE sl.used_ids IS NOT NULL
            GROUP BY m.id
        """)

        most_helpful = conn.execute("""
            SELECT
                mem_id as id,
                content,
                category,
                retrieve_count,
                used_count,
                CAST(used_count AS REAL) / retrieve_count as hit_rate
            FROM memory_feedback
            WHERE retrieve_count >= 5
            ORDER BY hit_rate DESC, used_count DESC
            LIMIT 10
        """).fetchall()
        stats['most_helpful'] = [dict(row) for row in most_helpful]

        # Least helpful (retrieved often but rarely used)
        least_helpful = conn.execute("""
            SELECT
                mem_id as id,
                content,
                category,
                retrieve_count,
                used_count,
                CAST(used_count AS REAL) / retrieve_count as hit_rate
            FROM memory_feedback
            WHERE retrieve_count >= 10
            ORDER BY hit_rate ASC, retrieve_count DESC
            LIMIT 10
        """).fetchall()
        stats['least_helpful'] = [dict(row) for row in least_helpful]

        conn.execute("DROP TABLE IF EXISTS memory_feedback")
    except (sqlite3.OperationalError, sqlite3.Error) as e:
        logger.warning(f"Could not calculate memory feedback stats: {e}")
        stats['most_helpful'] = []
        stats['least_helpful'] = []

    # Search patterns (most common queries)
    try:
        patterns = conn.execute("""
            SELECT
                query,
                COUNT(*) as search_count,
                AVG(hit_rate) as avg_hit_rate,
                AVG(result_count) as avg_results
            FROM search_log
            WHERE used_ids IS NOT NULL
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT 20
        """).fetchall()
        stats['search_patterns'] = [dict(row) for row in patterns]
    except sqlite3.OperationalError:
        stats['search_patterns'] = []

    # Failing queries (0% hit rate)
    try:
        failing = conn.execute("""
            SELECT query, search_type, result_count, created_at
            FROM search_log
            WHERE used_ids IS NOT NULL AND hit_rate = 0.0
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        stats['failing_queries'] = [dict(row) for row in failing]
    except sqlite3.OperationalError:
        stats['failing_queries'] = []

    conn.close()
    return stats


def log_usage(conn: Any, memory_id: int, search_id: Optional[int] = None,
              context: str = "retrieved") -> None:
    """Log that a memory was actually used (not just retrieved).

    Updates the search_log to track which memories were actually useful.
    Increments access_count as a side effect (already handled by touch_memory).

    Args:
        conn: Database connection
        memory_id: ID of the memory that was used
        search_id: ID of the search that led to this usage (optional)
        context: Context of usage (retrieved, viewed, applied)
    """
    if search_id:
        # Get current used_ids for this search
        row = conn.execute("""
            SELECT used_ids, result_ids, result_count
            FROM search_log WHERE id = ?
        """, (search_id,)).fetchone()

        if row:
            used_ids = row['used_ids'] or ''
            used_set = set(filter(None, used_ids.split(',')))
            used_set.add(str(memory_id))
            new_used_ids = ','.join(used_set)

            # Calculate hit rate
            used_count = len(used_set)
            result_count = row['result_count'] or 0
            hit_rate = used_count / result_count if result_count > 0 else 0.0

            conn.execute("""
                UPDATE search_log
                SET used_ids = ?, hit_rate = ?
                WHERE id = ?
            """, (new_used_ids, hit_rate, search_id))
            conn.commit()


def log_miss(conn: Any, query: str, context: str = "no_results") -> None:
    """Log that a search returned no useful results.

    This helps identify knowledge gaps where new memories should be added.

    Args:
        conn: Database connection
        query: The query that had no results
        context: Why it was a miss (no_results, ignored, not_relevant)
    """
    # Log as a zero-result search
    conn.execute("""
        INSERT INTO search_log (query, search_type, result_count, hit_rate)
        VALUES (?, ?, 0, 0.0)
    """, (query, context))
    conn.commit()


def get_improvement_suggestions(conn: Optional[Any] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Analyze search logs and suggest improvements.

    Returns:
        Dictionary containing:
        - merge_candidates: Memories that should be merged (similar search patterns)
        - tag_suggestions: Tags that should be added based on common search terms
        - deprecation_candidates: Memories that should be deprecated (never useful)
        - knowledge_gaps: Queries with 0 results (missing knowledge)
    """
    if conn is None:
        conn = get_db()
        should_close = True
    else:
        should_close = False

    suggestions = {}

    try:
        # 1. Deprecation candidates: memories never used despite multiple retrievals
        deprecation = conn.execute("""
            SELECT
                mem_id as id,
                content,
                category,
                retrieve_count
            FROM (
                SELECT
                    CAST(value AS INTEGER) as mem_id,
                    COUNT(*) as retrieve_count,
                    SUM(CASE WHEN sl.used_ids LIKE '%' || value || '%' THEN 1 ELSE 0 END) as used_count
                FROM search_log sl, json_each('["' || REPLACE(sl.result_ids, ',', '","') || '"]')
                WHERE sl.result_ids IS NOT NULL AND sl.used_ids IS NOT NULL
                GROUP BY mem_id
                HAVING retrieve_count >= 5 AND used_count = 0
            ) stats
            JOIN memories m ON m.id = stats.mem_id
            WHERE m.active = 1
            ORDER BY retrieve_count DESC
            LIMIT 10
        """).fetchall()

        suggestions['deprecation_candidates'] = [
            {
                'id': r['id'],
                'content': r['content'][:80] + '...' if len(r['content']) > 80 else r['content'],
                'category': r['category'],
                'retrieved_count': r['retrieve_count'],
                'reason': 'Retrieved multiple times but never used'
            }
            for r in deprecation
        ]

        # 2. Knowledge gaps: queries with zero results
        gaps = conn.execute("""
            SELECT query, search_type, COUNT(*) as attempt_count
            FROM search_log
            WHERE result_count = 0
            GROUP BY query
            ORDER BY attempt_count DESC
            LIMIT 10
        """).fetchall()

        suggestions['knowledge_gaps'] = [
            {
                'query': r['query'],
                'search_type': r['search_type'],
                'attempt_count': r['attempt_count'],
                'reason': 'No memories found for this query'
            }
            for r in gaps
        ]

        # 3. Tag suggestions: extract common search terms
        # This is a simplified version - could be enhanced with NLP
        tag_suggestions = []
        common_queries = conn.execute("""
            SELECT query, COUNT(*) as search_count
            FROM search_log
            WHERE result_count > 0 AND hit_rate > 0.3
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT 20
        """).fetchall()

        import re
        for row in common_queries:
            # Extract potential tags (simple tokenization)
            words = re.findall(r'\b\w{4,}\b', row['query'].lower())
            for word in words:
                tag_suggestions.append({
                    'keyword': word,
                    'search_count': row['search_count'],
                    'reason': 'Commonly searched term'
                })

        # Deduplicate and sort
        seen = set()
        unique_tags = []
        for tag in tag_suggestions:
            if tag['keyword'] not in seen:
                seen.add(tag['keyword'])
                unique_tags.append(tag)

        suggestions['tag_suggestions'] = sorted(
            unique_tags,
            key=lambda x: x['search_count'],
            reverse=True
        )[:10]

        # 4. Merge candidates placeholder (would need more sophisticated logic)
        suggestions['merge_candidates'] = []

    except (sqlite3.OperationalError, sqlite3.Error) as e:
        logger.warning(f"Could not generate improvement suggestions: {e}")
        suggestions = {
            'deprecation_candidates': [],
            'knowledge_gaps': [],
            'tag_suggestions': [],
            'merge_candidates': []
        }

    if should_close:
        conn.close()

    return suggestions


def auto_feedback_from_session(session_transcript_path: str, conn: Optional[Any] = None) -> Dict[str, int]:
    """Parse a session transcript to extract feedback signals.

    Analyzes the session to find:
    1. search commands → what was searched
    2. get commands after search → what was used (creates positive feedback)
    3. add commands after failed search → what was missing (knowledge gap)

    Args:
        session_transcript_path: Path to session transcript JSON file
        conn: Database connection (optional)

    Returns:
        Dictionary with feedback stats (searches, uses, gaps)
    """
    if conn is None:
        conn = get_db()
        should_close = True
    else:
        should_close = False

    stats = {'searches': 0, 'uses': 0, 'gaps': 0}

    try:
        from pathlib import Path
        import json

        transcript_path = Path(session_transcript_path)
        if not transcript_path.exists():
            if should_close:
                conn.close()
            return stats

        with open(transcript_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        last_search_id = None

        for line in lines:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Look for tool calls
            if entry.get('type') != 'tool_use':
                continue

            tool_name = entry.get('name', '')
            tool_input = entry.get('input', {})

            # Detect search command
            if 'search' in tool_name.lower():
                query = tool_input.get('query', '') or tool_input.get('pattern', '')
                if query:
                    # Log this search (simplified - in real usage, result_ids come from actual search)
                    cursor = conn.execute("""
                        INSERT INTO search_log (query, search_type, result_ids, result_count)
                        VALUES (?, 'transcript', '', 0)
                    """, (query,))
                    last_search_id = cursor.lastrowid
                    stats['searches'] += 1

            # Detect get/read after search (usage signal)
            elif ('get' in tool_name.lower() or 'read' in tool_name.lower()) and last_search_id:
                # Extract memory ID if present
                mem_id = tool_input.get('id') or tool_input.get('memory_id')
                if mem_id:
                    log_usage(conn, int(mem_id), last_search_id, 'transcript')
                    stats['uses'] += 1

            # Detect add command after failed search (gap signal)
            elif 'add' in tool_name.lower() and last_search_id:
                # This was added because search failed → knowledge gap
                stats['gaps'] += 1

        conn.commit()

    except Exception as e:
        logger.warning(f"Error parsing session transcript: {e}")

    if should_close:
        conn.close()

    return stats


def apply_feedback_learning(conn: Optional[Any] = None) -> Dict[str, int]:
    """Apply learning from search feedback. Run nightly via dream.

    - Memories with high hit rate (>80% over 10+ searches) → boost priority +1
    - Memories with low hit rate (<20% over 10+ searches) → decay priority -1
    - Memories retrieved 20+ times but never used → flag as stale

    Returns:
        Dict with counts: boosted, decayed, flagged
    """
    if conn is None:
        conn = get_db()
        should_close = True
    else:
        should_close = False

    results = {'boosted': 0, 'decayed': 0, 'flagged': 0}

    try:
        # Build temp table of memory feedback stats
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS memory_feedback_stats AS
            SELECT
                mem_id,
                COUNT(*) as retrieve_count,
                SUM(used_count) as total_used
            FROM (
                SELECT
                    CAST(value AS INTEGER) as mem_id,
                    sl.id as search_id,
                    CASE WHEN sl.used_ids LIKE '%' || value || '%' THEN 1 ELSE 0 END as used_count
                FROM search_log sl, json_each('["' || REPLACE(sl.result_ids, ',', '","') || '"]')
                WHERE sl.result_ids IS NOT NULL AND sl.used_ids IS NOT NULL
            )
            GROUP BY mem_id
        """)

        # High performers: >80% hit rate over 10+ searches → boost priority
        boosted_ids = conn.execute("""
            SELECT mem_id
            FROM memory_feedback_stats
            WHERE retrieve_count >= 10
            AND CAST(total_used AS REAL) / retrieve_count > 0.80
        """).fetchall()

        for row in boosted_ids:
            conn.execute("""
                UPDATE memories
                SET priority = MIN(10, priority + 1)
                WHERE id = ?
            """, (row['mem_id'],))
            results['boosted'] += 1

        # Low performers: <20% hit rate over 10+ searches → decay priority
        decayed_ids = conn.execute("""
            SELECT mem_id
            FROM memory_feedback_stats
            WHERE retrieve_count >= 10
            AND CAST(total_used AS REAL) / retrieve_count < 0.20
        """).fetchall()

        for row in decayed_ids:
            conn.execute("""
                UPDATE memories
                SET priority = MAX(0, priority - 1)
                WHERE id = ?
            """, (row['mem_id'],))
            results['decayed'] += 1

        # Never used: retrieved 20+ times but never used → flag as stale
        flagged_ids = conn.execute("""
            SELECT mem_id
            FROM memory_feedback_stats
            WHERE retrieve_count >= 20 AND total_used = 0
        """).fetchall()

        for row in flagged_ids:
            conn.execute("""
                UPDATE memories
                SET stale = 1
                WHERE id = ?
            """, (row['mem_id'],))
            results['flagged'] += 1

        conn.execute("DROP TABLE IF EXISTS memory_feedback_stats")
        conn.commit()

        logger.info(f"Feedback learning applied: {results['boosted']} boosted, {results['decayed']} decayed, {results['flagged']} flagged")

    except (sqlite3.OperationalError, sqlite3.Error) as e:
        logger.warning(f"Could not apply feedback learning: {e}")

    if should_close:
        conn.close()

    return results
