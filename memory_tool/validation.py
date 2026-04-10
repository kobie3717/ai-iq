"""Drift detection and validation module for reinforced lies problem.

This module addresses the critical issue where frequently accessed but incorrect
memories become self-reinforcing. The more a wrong memory is cited, the stronger
it becomes - turning lies into "proven truth" through access patterns alone.

Drift detection identifies high-risk memories that need human validation.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from .config import get_logger
from .database import has_vec_support

logger = get_logger(__name__)


def score_drift_risk(memory_row: dict) -> float:
    """Calculate drift risk score (0.0-1.0) for a memory.

    Higher score = higher risk of being a reinforced lie.

    Risk factors:
    - High access count (self-reinforcement)
    - Old age (stale information risk)
    - No citations (unverified claims)
    - Semantic tier (most "trusted" = highest risk if wrong)
    - Never validated

    Args:
        memory_row: dict with keys: access_count, created_at, citations, tier,
                   last_validated_at, proof_count

    Returns:
        Risk score 0.0 (low risk) to 1.0 (high risk)
    """
    risk = 0.0

    # Factor 1: Access count (high = self-reinforcing)
    # Scale: 0 accesses = 0.0, 10+ accesses = 0.3
    access_count = memory_row.get('access_count', 0)
    risk += min(access_count / 30.0, 0.3)

    # Factor 2: Age (older = more stale risk)
    # Scale: <30d = 0.0, >180d = 0.25
    created_at = memory_row.get('created_at')
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
            age_days = (datetime.now() - created).days
            risk += min(age_days / 720.0, 0.25)  # 720d = max aging factor
        except (ValueError, AttributeError):
            pass

    # Factor 3: No citations (unverified)
    # Scale: no citations = 0.2, has citations = 0.0
    citations = memory_row.get('citations', '')
    if not citations or citations.strip() == '':
        risk += 0.2

    # Factor 4: Semantic tier (most trusted = highest risk)
    # Scale: semantic = 0.15, episodic = 0.05, working = 0.0
    tier = memory_row.get('tier', 'episodic')
    if tier == 'semantic':
        risk += 0.15
    elif tier == 'episodic':
        risk += 0.05

    # Factor 5: Never validated
    # Scale: never validated = 0.1, validated = 0.0
    last_validated = memory_row.get('last_validated_at')
    if not last_validated:
        risk += 0.1

    return min(risk, 1.0)


def find_drift_candidates(
    conn: sqlite3.Connection,
    min_access_count: int = 5,
    min_age_days: int = 30
) -> List[Dict]:
    """Find memories that need validation review.

    Identifies high-access, old memories that might be reinforced lies.

    Args:
        conn: Database connection
        min_access_count: Minimum access count to consider (default 5)
        min_age_days: Minimum age in days (default 30)

    Returns:
        List of memory dicts with risk scores, sorted by risk descending
    """
    cutoff_date = (datetime.now() - timedelta(days=min_age_days)).isoformat()

    # Find candidate memories
    query = """
        SELECT
            id,
            category,
            content,
            tier,
            access_count,
            created_at,
            citations,
            last_validated_at,
            proof_count
        FROM memories
        WHERE active = 1
        AND access_count >= ?
        AND created_at < ?
        ORDER BY access_count DESC
        LIMIT 100
    """

    rows = conn.execute(query, (min_access_count, cutoff_date)).fetchall()

    # Score each memory
    candidates = []
    for row in rows:
        row_dict = dict(row)
        row_dict['drift_risk'] = score_drift_risk(row_dict)
        candidates.append(row_dict)

    # Sort by risk score descending
    candidates.sort(key=lambda x: x['drift_risk'], reverse=True)

    return candidates


def mark_validated(
    conn: sqlite3.Connection,
    memory_id: int,
    validator: str = 'user',
    validation_type: str = 'user',
    result: str = 'confirmed',
    notes: str = ''
) -> bool:
    """Mark a memory as validated with human review.

    Args:
        conn: Database connection
        memory_id: Memory ID to validate
        validator: Who validated (default 'user')
        validation_type: Type of validation (user|external_source|llm_check|cross_reference)
        result: Validation result (confirmed|refuted|uncertain)
        notes: Optional notes about validation

    Returns:
        True if successful, False if memory not found
    """
    # Check memory exists
    mem = conn.execute("SELECT id FROM memories WHERE id = ? AND active = 1", (memory_id,)).fetchone()
    if not mem:
        logger.warning(f"Memory #{memory_id} not found")
        return False

    # Update last_validated_at timestamp
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE memories SET last_validated_at = ? WHERE id = ?",
        (now, memory_id)
    )

    # Add validation log entry
    conn.execute("""
        INSERT INTO validation_log (memory_id, validator, validation_type, result, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (memory_id, validator, validation_type, result, notes))

    conn.commit()
    logger.info(f"Validated memory #{memory_id} as {result} by {validator}")
    return True


def mark_refuted(
    conn: sqlite3.Connection,
    memory_id: int,
    validator: str = 'user',
    notes: str = ''
) -> bool:
    """Mark a memory as refuted (wrong) and demote tier.

    Refuted memories are demoted from semantic -> episodic -> working
    to reduce their authority and prevent further reinforcement.

    Args:
        conn: Database connection
        memory_id: Memory ID to refute
        validator: Who refuted it
        notes: Why it's wrong

    Returns:
        True if successful, False if memory not found
    """
    # Get current tier
    mem = conn.execute(
        "SELECT id, tier FROM memories WHERE id = ? AND active = 1",
        (memory_id,)
    ).fetchone()

    if not mem:
        logger.warning(f"Memory #{memory_id} not found")
        return False

    current_tier = mem['tier'] or 'episodic'

    # Demote tier: semantic -> episodic -> working
    if current_tier == 'semantic':
        new_tier = 'episodic'
    elif current_tier == 'episodic':
        new_tier = 'working'
    else:
        new_tier = 'working'

    # Update tier and validation timestamp
    now = datetime.now().isoformat()
    conn.execute("""
        UPDATE memories
        SET tier = ?, last_validated_at = ?
        WHERE id = ?
    """, (new_tier, now, memory_id))

    # Log the refutation
    conn.execute("""
        INSERT INTO validation_log (memory_id, validator, validation_type, result, notes)
        VALUES (?, ?, 'user', 'refuted', ?)
    """, (memory_id, validator, notes))

    conn.commit()
    logger.info(f"Refuted memory #{memory_id}, demoted {current_tier} -> {new_tier}")
    return True


def get_unvalidated_semantic(conn: sqlite3.Connection) -> List[Dict]:
    """Get semantic tier memories that have never been validated.

    Semantic tier is supposed to be "proven knowledge" but if it's never
    been validated, it might be a reinforced lie.

    Args:
        conn: Database connection

    Returns:
        List of unvalidated semantic memories
    """
    query = """
        SELECT
            id,
            category,
            content,
            tier,
            access_count,
            created_at,
            citations,
            proof_count
        FROM memories
        WHERE active = 1
        AND tier = 'semantic'
        AND (last_validated_at IS NULL OR last_validated_at = '')
        ORDER BY access_count DESC
        LIMIT 50
    """

    rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def detect_contradictions_in_tier(
    conn: sqlite3.Connection,
    tier: str = 'semantic',
    threshold: float = 0.75
) -> List[Tuple[Dict, Dict, float]]:
    """Find contradicting memories within a tier using semantic search.

    Contradictions in semantic tier are especially dangerous - they indicate
    that proven "facts" disagree with each other.

    Args:
        conn: Database connection
        tier: Which tier to check (default 'semantic')
        threshold: Similarity threshold for considering contradiction (default 0.75)

    Returns:
        List of (memory1, memory2, similarity_score) tuples
    """
    # Get all memories in tier
    query = """
        SELECT id, content, tier
        FROM memories
        WHERE active = 1
        AND tier = ?
        ORDER BY access_count DESC
        LIMIT 100
    """

    memories = [dict(row) for row in conn.execute(query, (tier,)).fetchall()]

    # Look for contradictions using semantic search if available
    contradictions = []

    if has_vec_support():
        try:
            from .embedding import semantic_search

            # For each memory, find similar ones and check for negation patterns
            for mem in memories:
                # Find semantically similar memories
                similar = semantic_search(
                    conn,
                    mem['content'],
                    limit=5,
                    min_similarity=threshold
                )

                # Check for negation patterns
                negation_patterns = [
                    r'\b(not|no|never|without|except)\b',
                    r'\b(don\'t|doesn\'t|didn\'t|won\'t|can\'t)\b',
                    r'\b(avoid|prevent|disable|remove)\b'
                ]

                content_lower = mem['content'].lower()
                has_negation = any(
                    __import__('re').search(pat, content_lower)
                    for pat in negation_patterns
                )

                for sim_mem in similar:
                    # Skip self
                    if sim_mem['id'] == mem['id']:
                        continue

                    # Check if similar memory has opposite negation
                    sim_lower = sim_mem['content'].lower()
                    sim_has_negation = any(
                        __import__('re').search(pat, sim_lower)
                        for pat in negation_patterns
                    )

                    # If one has negation and other doesn't, likely contradiction
                    if has_negation != sim_has_negation:
                        contradictions.append((
                            mem,
                            sim_mem,
                            sim_mem.get('similarity', 0.0)
                        ))

        except ImportError:
            logger.debug("Vector search not available for contradiction detection")

    # Deduplicate (A,B) and (B,A)
    seen = set()
    unique_contradictions = []
    for m1, m2, score in contradictions:
        pair = tuple(sorted([m1['id'], m2['id']]))
        if pair not in seen:
            seen.add(pair)
            unique_contradictions.append((m1, m2, score))

    return unique_contradictions


def validation_report(conn: sqlite3.Connection) -> Dict:
    """Generate validation statistics report.

    Args:
        conn: Database connection

    Returns:
        Dict with validation stats
    """
    # Count validations by result
    validation_counts = conn.execute("""
        SELECT result, COUNT(*) as count
        FROM validation_log
        GROUP BY result
    """).fetchall()

    validation_by_result = {row['result']: row['count'] for row in validation_counts}

    # Count memories by validation status and tier
    tier_validation = conn.execute("""
        SELECT
            tier,
            COUNT(*) as total,
            SUM(CASE WHEN last_validated_at IS NOT NULL THEN 1 ELSE 0 END) as validated
        FROM memories
        WHERE active = 1
        GROUP BY tier
    """).fetchall()

    tier_stats = {}
    for row in tier_validation:
        tier = row['tier'] or 'episodic'
        total = row['total']
        validated = row['validated']
        tier_stats[tier] = {
            'total': total,
            'validated': validated,
            'unvalidated': total - validated,
            'pct_validated': round(100 * validated / total, 1) if total > 0 else 0
        }

    # High-risk memories needing validation
    high_risk = find_drift_candidates(conn, min_access_count=5, min_age_days=30)
    high_risk_count = len([m for m in high_risk if m['drift_risk'] > 0.6])

    return {
        'validation_counts': validation_by_result,
        'tier_stats': tier_stats,
        'high_risk_count': high_risk_count,
        'total_validations': sum(validation_by_result.values())
    }
