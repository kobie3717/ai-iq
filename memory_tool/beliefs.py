"""Belief and prediction system for AI-IQ memory."""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging

from .database import get_db
from .config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Core Belief Operations
# ============================================================================

def set_confidence(db: sqlite3.Connection, memory_id: int, confidence: float, reason: str) -> None:
    """Set confidence for a memory with logging.

    Args:
        db: Database connection
        memory_id: ID of the memory
        confidence: Confidence value (0.01-0.99)
        reason: Reason for setting confidence
    """
    # Clamp confidence to valid range
    confidence = max(0.01, min(0.99, confidence))

    # Get current confidence
    row = db.execute("SELECT confidence FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        logger.warning(f"Memory #{memory_id} not found")
        return

    old_confidence = row['confidence'] or 0.7

    # Update confidence
    db.execute("""
        UPDATE memories SET confidence = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (confidence, memory_id))

    # Log the update
    db.execute("""
        INSERT INTO belief_updates (memory_id, old_confidence, new_confidence, reason)
        VALUES (?, ?, ?, ?)
    """, (memory_id, old_confidence, confidence, reason))

    # Log to timeline (Feature 2)
    try:
        db.execute("""
            INSERT INTO belief_timeline (memory_id, old_confidence, new_confidence, reason, source_type)
            VALUES (?, ?, ?, ?, 'manual')
        """, (memory_id, old_confidence, confidence, reason))
    except Exception:
        pass  # Timeline table might not exist yet

    db.commit()
    logger.debug(f"Set confidence for memory #{memory_id}: {old_confidence:.2f} → {confidence:.2f} ({reason})")


def get_confidence(db: sqlite3.Connection, memory_id: int) -> float:
    """Get confidence for a memory.

    Args:
        db: Database connection
        memory_id: ID of the memory

    Returns:
        Confidence value (0.01-0.99, default 0.7)
    """
    row = db.execute("SELECT confidence FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        return 0.7  # Default
    return row['confidence'] or 0.7


def boost_confidence(db: sqlite3.Connection, memory_id: int, amount: float, reason: str) -> float:
    """Boost confidence by a specified amount.

    Args:
        db: Database connection
        memory_id: ID of the memory
        amount: Amount to boost (positive float)
        reason: Reason for boosting

    Returns:
        New confidence value
    """
    current = get_confidence(db, memory_id)
    new_confidence = min(0.99, current + abs(amount))
    set_confidence(db, memory_id, new_confidence, reason)
    return new_confidence


def weaken_confidence(db: sqlite3.Connection, memory_id: int, amount: float, reason: str) -> float:
    """Weaken confidence by a specified amount.

    Args:
        db: Database connection
        memory_id: ID of the memory
        amount: Amount to weaken (positive float)
        reason: Reason for weakening

    Returns:
        New confidence value
    """
    current = get_confidence(db, memory_id)
    new_confidence = max(0.01, current - abs(amount))
    set_confidence(db, memory_id, new_confidence, reason)
    return new_confidence


# ============================================================================
# Prediction Lifecycle
# ============================================================================

def predict(
    db: sqlite3.Connection,
    prediction: str,
    based_on: Optional[int] = None,
    confidence: float = 0.5,
    deadline: Optional[str] = None,
    expected_outcome: str = ""
) -> int:
    """Create a prediction based on a belief.

    Args:
        db: Database connection
        prediction: The prediction statement
        based_on: Memory ID that this prediction is based on (optional)
        confidence: Confidence in the prediction (0.0-1.0)
        deadline: ISO date string (YYYY-MM-DD) for when to check outcome
        expected_outcome: What is expected to happen

    Returns:
        Prediction ID
    """
    # Clamp confidence
    confidence = max(0.01, min(0.99, confidence))

    cursor = db.execute("""
        INSERT INTO predictions (
            memory_id, prediction, expected_outcome, confidence, deadline, status
        ) VALUES (?, ?, ?, ?, ?, 'open')
    """, (based_on, prediction, expected_outcome, confidence, deadline))

    prediction_id = cursor.lastrowid
    db.commit()

    logger.info(f"Created prediction #{prediction_id}: {prediction[:60]}... (confidence: {confidence:.2f})")
    return prediction_id


def resolve_prediction(
    db: sqlite3.Connection,
    prediction_id: int,
    actual_outcome: str,
    confirmed: bool
) -> Dict[str, Any]:
    """Resolve a prediction and propagate belief updates.

    Args:
        db: Database connection
        prediction_id: ID of the prediction
        actual_outcome: What actually happened
        confirmed: True if prediction was confirmed, False if refuted

    Returns:
        Dictionary with update summary
    """
    # Get prediction details
    pred = db.execute("""
        SELECT memory_id, prediction, confidence, expected_outcome
        FROM predictions WHERE id = ?
    """, (prediction_id,)).fetchone()

    if not pred:
        logger.warning(f"Prediction #{prediction_id} not found")
        return {'updated': 0, 'source_memory': None}

    # Update prediction status
    status = 'confirmed' if confirmed else 'refuted'
    db.execute("""
        UPDATE predictions SET
            status = ?,
            actual_outcome = ?,
            resolved_at = datetime('now')
        WHERE id = ?
    """, (status, actual_outcome, prediction_id))

    updated_memories = []

    # Update source memory confidence
    if pred['memory_id']:
        source_id = pred['memory_id']
        if confirmed:
            new_conf = boost_confidence(
                db, source_id, 0.1,
                f"Prediction #{prediction_id} confirmed"
            )
            updated_memories.append(source_id)
            logger.info(f"Prediction confirmed → boosted memory #{source_id} confidence")

            # Propagate positive update through causal graph
            propagated = propagate_belief_update(db, source_id, 0.05)
            updated_memories.extend(propagated)
        else:
            new_conf = weaken_confidence(
                db, source_id, 0.2,
                f"Prediction #{prediction_id} refuted"
            )
            updated_memories.append(source_id)
            logger.info(f"Prediction refuted → weakened memory #{source_id} confidence")

            # Propagate negative update through causal graph
            propagated = propagate_belief_update(db, source_id, -0.1)
            updated_memories.extend(propagated)

    # Auto-transition belief lifecycle states
    try:
        from .beliefs_extended import auto_transition_on_prediction
        transitioned = auto_transition_on_prediction(db, prediction_id, confirmed)
        if transitioned:
            logger.info(f"Auto-transitioned {len(transitioned)} belief states")
    except ImportError:
        pass  # beliefs_extended might not be available

    db.commit()

    return {
        'updated': len(set(updated_memories)),
        'source_memory': pred['memory_id'],
        'propagated_to': list(set(updated_memories))
    }


def list_predictions(db: sqlite3.Connection, status: str = 'open') -> List[Dict[str, Any]]:
    """List predictions by status.

    Args:
        db: Database connection
        status: Filter by status (open, confirmed, refuted, expired, or 'all')

    Returns:
        List of prediction dictionaries
    """
    if status == 'all':
        query = "SELECT * FROM predictions ORDER BY created_at DESC"
        rows = db.execute(query).fetchall()
    else:
        query = "SELECT * FROM predictions WHERE status = ? ORDER BY created_at DESC"
        rows = db.execute(query, (status,)).fetchall()

    return [dict(row) for row in rows]


def expired_predictions(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Get predictions that are past their deadline but still open.

    Args:
        db: Database connection

    Returns:
        List of expired prediction dictionaries
    """
    now = datetime.now().isoformat()
    rows = db.execute("""
        SELECT * FROM predictions
        WHERE status = 'open'
        AND deadline IS NOT NULL
        AND deadline < ?
        ORDER BY deadline ASC
    """, (now,)).fetchall()

    return [dict(row) for row in rows]


# ============================================================================
# Bayesian Belief Propagation
# ============================================================================

def propagate_belief_update(
    db: sqlite3.Connection,
    memory_id: int,
    direction: float
) -> List[int]:
    """Propagate belief update through causal graph.

    Follows memory_relations edges to update connected beliefs.
    Positive direction = strengthen, negative = weaken.

    Args:
        db: Database connection
        memory_id: Source memory ID
        direction: Update direction (+/- float)

    Returns:
        List of updated memory IDs
    """
    updated_ids = []

    # Find causally connected memories through memory_relations
    # relation_types: related, supersedes, blocks, etc.
    # For now, we propagate through 'related' connections

    # Get directly related memories
    related = db.execute("""
        SELECT target_id, relation_type FROM memory_relations
        WHERE source_id = ? AND relation_type IN ('related', 'blocks')
    """, (memory_id,)).fetchall()

    for rel in related:
        target_id = rel['target_id']
        rel_type = rel['relation_type']

        # Scale the propagation based on relationship type
        if rel_type == 'blocks':
            # If A blocks B, and A is weakened, B might be strengthened (inverse)
            scaled_direction = -direction * 0.5
        else:
            # For 'related', propagate in same direction but attenuated
            scaled_direction = direction * 0.7

        # Apply update
        current = get_confidence(db, target_id)
        new_conf = max(0.01, min(0.99, current + scaled_direction))

        if abs(new_conf - current) > 0.01:  # Only update if significant
            set_confidence(
                db, target_id, new_conf,
                f"Propagated from memory #{memory_id} via {rel_type}"
            )
            updated_ids.append(target_id)

    if updated_ids:
        logger.debug(f"Propagated belief update from #{memory_id} to {len(updated_ids)} memories")

    return updated_ids


# ============================================================================
# Belief Analysis
# ============================================================================

def belief_conflicts(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Find high-confidence memories that contradict each other.

    Args:
        db: Database connection

    Returns:
        List of conflict dictionaries
    """
    # Get high-confidence active memories
    high_conf = db.execute("""
        SELECT id, content, category, project, confidence
        FROM memories
        WHERE active = 1 AND confidence > 0.7
        ORDER BY confidence DESC
    """).fetchall()

    conflicts = []

    # Check for contradictions using simple negation detection
    negation_patterns = [
        (r'\bnot\b', r'\bis\b'),
        (r'\bdon\'t\b', r'\bdo\b'),
        (r'\bdoesn\'t\b', r'\bdoes\b'),
        (r'\bfalse\b', r'\btrue\b'),
        (r'\bnever\b', r'\balways\b'),
        (r'\bno\b', r'\byes\b'),
    ]

    import re
    from difflib import SequenceMatcher

    seen_pairs = set()
    for i, a in enumerate(high_conf):
        for b in high_conf[i+1:]:
            if a['category'] != b['category']:
                continue

            # Check if contents are similar but with negations
            ratio = SequenceMatcher(None, a['content'].lower(), b['content'].lower()).ratio()

            # High similarity but look for negation patterns
            if ratio > 0.6:
                a_text = a['content'].lower()
                b_text = b['content'].lower()

                has_negation = False
                for neg_pattern, pos_pattern in negation_patterns:
                    if (re.search(neg_pattern, a_text) and re.search(pos_pattern, b_text)) or \
                       (re.search(pos_pattern, a_text) and re.search(neg_pattern, b_text)):
                        has_negation = True
                        break

                if has_negation:
                    pair_key = tuple(sorted([a['id'], b['id']]))
                    if pair_key not in seen_pairs:
                        conflicts.append({
                            'id1': a['id'],
                            'id2': b['id'],
                            'content1': a['content'],
                            'content2': b['content'],
                            'confidence1': a['confidence'],
                            'confidence2': b['confidence'],
                            'similarity': ratio,
                            'category': a['category']
                        })
                        seen_pairs.add(pair_key)

    return conflicts


def weakest_beliefs(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get lowest confidence active memories.

    Args:
        db: Database connection
        limit: Maximum number to return

    Returns:
        List of memory dictionaries
    """
    rows = db.execute("""
        SELECT id, category, content, confidence, project, tags, created_at
        FROM memories
        WHERE active = 1 AND category IN ('belief', 'learning', 'decision')
        ORDER BY confidence ASC
        LIMIT ?
    """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def strongest_beliefs(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get highest confidence, most validated beliefs.

    Args:
        db: Database connection
        limit: Maximum number to return

    Returns:
        List of memory dictionaries
    """
    rows = db.execute("""
        SELECT id, category, content, confidence, project, tags, access_count, created_at
        FROM memories
        WHERE active = 1 AND category IN ('belief', 'learning', 'decision')
        ORDER BY confidence DESC, access_count DESC
        LIMIT ?
    """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def belief_history(db: sqlite3.Connection, memory_id: int) -> List[Dict[str, Any]]:
    """Get all confidence changes for a memory over time.

    Args:
        db: Database connection
        memory_id: ID of the memory

    Returns:
        List of belief update dictionaries
    """
    rows = db.execute("""
        SELECT id, old_confidence, new_confidence, reason, updated_at
        FROM belief_updates
        WHERE memory_id = ?
        ORDER BY updated_at ASC
    """, (memory_id,)).fetchall()

    return [dict(row) for row in rows]


# ============================================================================
# Integration with Existing Systems
# ============================================================================

def beliefs_decay(db: sqlite3.Connection) -> int:
    """Weaken beliefs that have no supporting evidence or predictions.

    Called during dream mode to decay unsupported beliefs.

    Args:
        db: Database connection

    Returns:
        Number of beliefs weakened
    """
    # Find beliefs with:
    # 1. No related predictions (no validation attempts)
    # 2. Low access count (not frequently referenced)
    # 3. Not recently accessed

    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

    candidates = db.execute("""
        SELECT m.id, m.confidence
        FROM memories m
        LEFT JOIN predictions p ON p.memory_id = m.id
        WHERE m.active = 1
        AND m.category IN ('belief', 'learning')
        AND m.access_count < 3
        AND (m.accessed_at IS NULL OR m.accessed_at < ?)
        AND p.id IS NULL
        GROUP BY m.id
        HAVING m.confidence > 0.3
    """, (thirty_days_ago,)).fetchall()

    weakened = 0
    for row in candidates:
        new_conf = weaken_confidence(
            db, row['id'], 0.05,
            "Decay: no supporting evidence or predictions"
        )
        weakened += 1

    db.commit()
    return weakened


def beliefs_dream(db: sqlite3.Connection) -> Dict[str, int]:
    """Belief consolidation during dream mode.

    - Merge similar beliefs
    - Resolve expired predictions
    - Propagate updates

    Args:
        db: Database connection

    Returns:
        Dictionary with consolidation stats
    """
    stats = {
        'merged': 0,
        'predictions_resolved': 0,
        'predictions_expired': 0,
        'beliefs_weakened': 0
    }

    # 1. Resolve expired predictions
    expired = expired_predictions(db)
    for pred in expired:
        # Mark as expired and weaken source memory slightly
        db.execute("""
            UPDATE predictions SET status = 'expired'
            WHERE id = ?
        """, (pred['id'],))

        if pred['memory_id']:
            weaken_confidence(
                db, pred['memory_id'], 0.05,
                f"Prediction #{pred['id']} expired without resolution"
            )
            stats['beliefs_weakened'] += 1

        stats['predictions_expired'] += 1

    # 2. Run regular belief decay
    decayed = beliefs_decay(db)
    stats['beliefs_weakened'] += decayed

    # 3. Merge highly similar beliefs (>90% similarity)
    from difflib import SequenceMatcher

    beliefs = db.execute("""
        SELECT id, content, confidence, access_count
        FROM memories
        WHERE active = 1 AND category IN ('belief', 'learning')
        ORDER BY confidence DESC
    """).fetchall()

    seen_ids = set()
    for i, a in enumerate(beliefs):
        if a['id'] in seen_ids:
            continue
        for b in beliefs[i+1:]:
            if b['id'] in seen_ids:
                continue

            ratio = SequenceMatcher(None, a['content'].lower(), b['content'].lower()).ratio()
            if ratio > 0.90:
                # Keep the higher confidence one
                keep_id = a['id'] if a['confidence'] >= b['confidence'] else b['id']
                discard_id = b['id'] if keep_id == a['id'] else a['id']

                # Transfer any predictions to the kept belief
                db.execute("""
                    UPDATE predictions SET memory_id = ?
                    WHERE memory_id = ?
                """, (keep_id, discard_id))

                # Soft delete discarded belief
                db.execute("UPDATE memories SET active = 0 WHERE id = ?", (discard_id,))

                seen_ids.add(discard_id)
                stats['merged'] += 1

    db.commit()
    return stats
