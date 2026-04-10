"""Belief and prediction system for AI-IQ memory.

This module provides two complementary belief systems:

1. SIMPLE SYSTEM: Uses memories.confidence directly (lightweight, no additional tables)
   - Functions: set_confidence, predict, resolve_prediction_memory, etc.
   - Works with existing memories table
   - Good for basic confidence tracking

2. EXTENDED SYSTEM: Separate beliefs table with evidence tracking (advanced)
   - Functions: add_belief, add_evidence, resolve_prediction_belief, etc.
   - Requires beliefs/evidence/belief_revisions tables
   - Supports Bayesian updates, evidence tracking, lifecycle states
   - Good for explicit belief management with provenance

Both systems can coexist. Use the simple system for lightweight confidence tracking,
and the extended system when you need explicit beliefs with evidence tracking.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging
import re
from difflib import SequenceMatcher

from .database import get_db
from .config import get_logger

logger = get_logger(__name__)


# ============================================================================
# SIMPLE SYSTEM: Memory-Based Confidence Tracking
# ============================================================================

# ----------------------------------------------------------------------------
# Core Operations
# ----------------------------------------------------------------------------

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


# ----------------------------------------------------------------------------
# Prediction Lifecycle (Simple System)
# ----------------------------------------------------------------------------

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


def resolve_prediction_memory(
    db: sqlite3.Connection,
    prediction_id: int,
    actual_outcome: str,
    confirmed: bool
) -> Dict[str, Any]:
    """Resolve a prediction and propagate belief updates (simple system).

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
        transitioned = auto_transition_on_prediction(db, prediction_id, confirmed)
        if transitioned:
            logger.info(f"Auto-transitioned {len(transitioned)} belief states")
    except Exception as e:
        logger.debug(f"Could not auto-transition: {e}")

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


# ----------------------------------------------------------------------------
# Bayesian Belief Propagation
# ----------------------------------------------------------------------------

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


# ----------------------------------------------------------------------------
# Belief Analysis (Simple System)
# ----------------------------------------------------------------------------

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


def weakest_beliefs_memory(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get lowest confidence active memories (simple system).

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


def strongest_beliefs_memory(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get highest confidence, most validated beliefs (simple system).

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


# ----------------------------------------------------------------------------
# Maintenance (Simple System)
# ----------------------------------------------------------------------------

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


# ============================================================================
# EXTENDED SYSTEM: Explicit Beliefs with Evidence Tracking
# ============================================================================

# ----------------------------------------------------------------------------
# Database Schema
# ----------------------------------------------------------------------------

def init_beliefs_tables(conn: sqlite3.Connection) -> None:
    """Initialize extended beliefs tables.

    This is called automatically by init_db() in database.py if the tables don't exist.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS beliefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id INTEGER REFERENCES memories(id),
            statement TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            category TEXT DEFAULT 'general',
            evidence_for INTEGER DEFAULT 0,
            evidence_against INTEGER DEFAULT 0,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'active',
            belief_state TEXT DEFAULT 'hypothesis'
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            belief_id INTEGER REFERENCES beliefs(id),
            memory_id INTEGER REFERENCES memories(id),
            direction TEXT NOT NULL CHECK(direction IN ('supports', 'contradicts')),
            strength REAL DEFAULT 0.5,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS belief_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            belief_id INTEGER REFERENCES beliefs(id),
            old_confidence REAL,
            new_confidence REAL,
            reason TEXT,
            revision_type TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_beliefs_category ON beliefs(category);
        CREATE INDEX IF NOT EXISTS idx_beliefs_status ON beliefs(status);
        CREATE INDEX IF NOT EXISTS idx_beliefs_confidence ON beliefs(confidence);
        CREATE INDEX IF NOT EXISTS idx_beliefs_memory ON beliefs(memory_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_belief ON evidence(belief_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_memory ON evidence(memory_id);
        CREATE INDEX IF NOT EXISTS idx_belief_revisions_belief ON belief_revisions(belief_id);
    """)
    conn.commit()


# ----------------------------------------------------------------------------
# Belief CRUD Operations
# ----------------------------------------------------------------------------

def add_belief(
    db: sqlite3.Connection,
    statement: str,
    confidence: float = 0.5,
    category: str = 'general',
    source: str = 'user',
    memory_id: Optional[int] = None
) -> int:
    """Add a new belief to the system (extended system).

    Args:
        db: Database connection
        statement: The belief statement in plain text
        confidence: Initial confidence (0.0-1.0, default 0.5)
        category: Belief category (domain/project/pattern/causal/general)
        source: Where belief originated (observation/prediction/user/inference)
        memory_id: Optional linked memory ID

    Returns:
        Belief ID
    """
    confidence = max(0.01, min(0.99, confidence))

    cursor = db.execute("""
        INSERT INTO beliefs (statement, confidence, category, source, memory_id)
        VALUES (?, ?, ?, ?, ?)
    """, (statement, confidence, category, source, memory_id))

    belief_id = cursor.lastrowid
    db.commit()

    logger.info(f"Added belief #{belief_id}: {statement[:60]}... (confidence: {confidence:.2f})")
    return belief_id


def get_belief(db: sqlite3.Connection, belief_id: int) -> Optional[Dict[str, Any]]:
    """Get full details for a belief.

    Args:
        db: Database connection
        belief_id: ID of the belief

    Returns:
        Belief dictionary or None if not found
    """
    row = db.execute("SELECT * FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
    if not row:
        return None

    belief = dict(row)

    # Get evidence counts
    evidence_stats = db.execute("""
        SELECT
            COUNT(CASE WHEN direction = 'supports' THEN 1 END) as supports_count,
            COUNT(CASE WHEN direction = 'contradicts' THEN 1 END) as contradicts_count,
            AVG(CASE WHEN direction = 'supports' THEN strength END) as avg_support_strength,
            AVG(CASE WHEN direction = 'contradicts' THEN strength END) as avg_contradict_strength
        FROM evidence WHERE belief_id = ?
    """, (belief_id,)).fetchone()

    belief.update(dict(evidence_stats))

    return belief


def list_beliefs(
    db: sqlite3.Connection,
    category: Optional[str] = None,
    status: str = 'active',
    min_confidence: Optional[float] = None
) -> List[Dict[str, Any]]:
    """List beliefs with optional filters.

    Args:
        db: Database connection
        category: Filter by category (optional)
        status: Filter by status (active/disproven/confirmed/archived)
        min_confidence: Minimum confidence threshold (optional)

    Returns:
        List of belief dictionaries
    """
    query = "SELECT * FROM beliefs WHERE status = ?"
    params: List[Any] = [status]

    if category:
        query += " AND category = ?"
        params.append(category)

    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)

    query += " ORDER BY confidence DESC, updated_at DESC"

    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_belief_confidence(
    db: sqlite3.Connection,
    belief_id: int,
    new_confidence: float,
    reason: str,
    revision_type: str = 'manual'
) -> None:
    """Update belief confidence with revision logging.

    Args:
        db: Database connection
        belief_id: ID of the belief
        new_confidence: New confidence value (0.0-1.0)
        reason: Reason for the update
        revision_type: Type of revision (evidence/prediction_outcome/decay/manual/contradiction)
    """
    new_confidence = max(0.01, min(0.99, new_confidence))

    # Get current confidence
    row = db.execute("SELECT confidence FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
    if not row:
        logger.warning(f"Belief #{belief_id} not found")
        return

    old_confidence = row['confidence']

    # Update belief
    db.execute("""
        UPDATE beliefs
        SET confidence = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (new_confidence, belief_id))

    # Log revision
    db.execute("""
        INSERT INTO belief_revisions (belief_id, old_confidence, new_confidence, reason, revision_type)
        VALUES (?, ?, ?, ?, ?)
    """, (belief_id, old_confidence, new_confidence, reason, revision_type))

    # Log to timeline (Feature 2)
    try:
        db.execute("""
            INSERT INTO belief_timeline (belief_id, old_confidence, new_confidence, reason, source_type)
            VALUES (?, ?, ?, ?, ?)
        """, (belief_id, old_confidence, new_confidence, reason, revision_type))
    except Exception:
        pass  # Timeline table might not exist yet

    db.commit()

    logger.debug(f"Updated belief #{belief_id}: {old_confidence:.2f} → {new_confidence:.2f} ({reason})")


def search_beliefs(db: sqlite3.Connection, query: str) -> List[Dict[str, Any]]:
    """Search beliefs using full-text search.

    Args:
        db: Database connection
        query: Search query

    Returns:
        List of matching belief dictionaries
    """
    # Simple LIKE search for now
    # Could be enhanced with FTS if needed
    rows = db.execute("""
        SELECT * FROM beliefs
        WHERE status = 'active' AND statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 20
    """, (f"%{query}%",)).fetchall()

    return [dict(row) for row in rows]


# ----------------------------------------------------------------------------
# Bayesian Confidence Updates with Evidence
# ----------------------------------------------------------------------------

def add_evidence(
    db: sqlite3.Connection,
    belief_id: int,
    memory_id: int,
    direction: str,
    strength: float = 0.5,
    note: Optional[str] = None
) -> None:
    """Add evidence for or against a belief and update confidence.

    Args:
        db: Database connection
        belief_id: ID of the belief
        memory_id: ID of the memory serving as evidence
        direction: 'supports' or 'contradicts'
        strength: Evidence strength (0.0-1.0, default 0.5)
        note: Optional note about the evidence
    """
    if direction not in ('supports', 'contradicts'):
        raise ValueError("direction must be 'supports' or 'contradicts'")

    strength = max(0.0, min(1.0, strength))

    # Add evidence record
    db.execute("""
        INSERT INTO evidence (belief_id, memory_id, direction, strength, note)
        VALUES (?, ?, ?, ?, ?)
    """, (belief_id, memory_id, direction, strength, note))

    # Update evidence counters
    db.execute(f"""
        UPDATE beliefs
        SET evidence_{direction.replace('contradicts', 'against').replace('supports', 'for')} =
            evidence_{direction.replace('contradicts', 'against').replace('supports', 'for')} + 1
        WHERE id = ?
    """, (belief_id,))

    db.commit()

    # Now update confidence using weighted evidence ratio
    belief = db.execute("""
        SELECT evidence_for, evidence_against FROM beliefs WHERE id = ?
    """, (belief_id,)).fetchone()

    # Get average strengths
    evidence_stats = db.execute("""
        SELECT
            AVG(CASE WHEN direction = 'supports' THEN strength ELSE NULL END) as avg_support,
            AVG(CASE WHEN direction = 'contradicts' THEN strength ELSE NULL END) as avg_contradict
        FROM evidence WHERE belief_id = ?
    """, (belief_id,)).fetchone()

    avg_support = evidence_stats['avg_support'] or 0.5
    avg_contradict = evidence_stats['avg_contradict'] or 0.5

    # Weighted evidence formula
    # new_confidence = (for * avg_for) / (for * avg_for + against * avg_against)
    for_count = belief['evidence_for']
    against_count = belief['evidence_against']

    if for_count + against_count > 0:
        weighted_for = for_count * avg_support
        weighted_against = against_count * avg_contradict
        new_confidence = weighted_for / (weighted_for + weighted_against)

        # Clamp to reasonable range
        new_confidence = max(0.01, min(0.99, new_confidence))

        update_belief_confidence(
            db, belief_id, new_confidence,
            f"Evidence added: {direction} (strength {strength:.2f})",
            revision_type='evidence'
        )

    logger.info(f"Added {direction} evidence to belief #{belief_id} (strength: {strength:.2f})")


def bayesian_update(
    db: sqlite3.Connection,
    belief_id: int,
    evidence_direction: str,
    evidence_strength: float
) -> float:
    """Simplified Bayesian update for a belief.

    Uses Bayes' theorem to update confidence based on new evidence:
    - If supports: new = old * strength / (old * strength + (1-old) * (1-strength))
    - If contradicts: new = old * (1-strength) / (old * (1-strength) + (1-old) * strength)

    Args:
        db: Database connection
        belief_id: ID of the belief
        evidence_direction: 'supports' or 'contradicts'
        evidence_strength: Strength of evidence (0.0-1.0)

    Returns:
        New confidence value
    """
    row = db.execute("SELECT confidence FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
    if not row:
        logger.warning(f"Belief #{belief_id} not found")
        return 0.5

    old_conf = row['confidence']
    evidence_strength = max(0.01, min(0.99, evidence_strength))

    if evidence_direction == 'supports':
        # Bayesian update for supporting evidence
        numerator = old_conf * evidence_strength
        denominator = old_conf * evidence_strength + (1 - old_conf) * (1 - evidence_strength)
    else:  # contradicts
        # Bayesian update for contradicting evidence
        numerator = old_conf * (1 - evidence_strength)
        denominator = old_conf * (1 - evidence_strength) + (1 - old_conf) * evidence_strength

    new_conf = numerator / denominator if denominator > 0 else old_conf
    new_conf = max(0.01, min(0.99, new_conf))

    update_belief_confidence(
        db, belief_id, new_conf,
        f"Bayesian update: {evidence_direction} (strength {evidence_strength:.2f})",
        revision_type='evidence'
    )

    return new_conf


# ----------------------------------------------------------------------------
# Prediction Integration (Extended System)
# ----------------------------------------------------------------------------

def make_prediction(
    db: sqlite3.Connection,
    belief_id: int,
    prediction_text: str,
    confidence: Optional[float] = None,
    deadline: Optional[str] = None
) -> int:
    """Make a prediction based on a belief (extended system).

    Args:
        db: Database connection
        belief_id: ID of the belief this prediction is based on
        prediction_text: What we predict will happen
        confidence: Predicted confidence (uses belief confidence if None)
        deadline: ISO date string for resolution deadline (optional)

    Returns:
        Prediction ID
    """
    # Get belief details
    belief = get_belief(db, belief_id)
    if not belief:
        raise ValueError(f"Belief #{belief_id} not found")

    if confidence is None:
        confidence = belief['confidence']

    confidence = max(0.01, min(0.99, confidence))

    # Create prediction using existing predictions table
    # Link to belief's memory_id if available
    cursor = db.execute("""
        INSERT INTO predictions (memory_id, prediction, confidence, deadline, status)
        VALUES (?, ?, ?, ?, 'open')
    """, (belief['memory_id'], prediction_text, confidence, deadline))

    prediction_id = cursor.lastrowid
    db.commit()

    logger.info(f"Created prediction #{prediction_id} based on belief #{belief_id}")
    return prediction_id


def resolve_prediction_belief(
    db: sqlite3.Connection,
    prediction_id: int,
    outcome: str,
    correct: bool
) -> Dict[str, Any]:
    """Resolve a prediction and update related beliefs (extended system).

    Args:
        db: Database connection
        prediction_id: ID of the prediction
        outcome: What actually happened
        correct: Whether the prediction was correct

    Returns:
        Dictionary with update statistics
    """
    # Get prediction
    pred = db.execute("""
        SELECT memory_id, confidence FROM predictions WHERE id = ?
    """, (prediction_id,)).fetchone()

    if not pred:
        logger.warning(f"Prediction #{prediction_id} not found")
        return {'updated_beliefs': 0}

    # Update prediction status
    status = 'confirmed' if correct else 'refuted'
    db.execute("""
        UPDATE predictions
        SET status = ?, actual_outcome = ?, resolved_at = datetime('now')
        WHERE id = ?
    """, (status, outcome, prediction_id))

    # Find beliefs linked to this prediction's memory
    updated_beliefs = []
    if pred['memory_id']:
        beliefs_to_update = db.execute("""
            SELECT id FROM beliefs WHERE memory_id = ? AND status = 'active'
        """, (pred['memory_id'],)).fetchall()

        for belief_row in beliefs_to_update:
            belief_id = belief_row['id']

            if correct:
                # Boost belief confidence
                bayesian_update(db, belief_id, 'supports', 0.7)
            else:
                # Weaken belief confidence
                bayesian_update(db, belief_id, 'contradicts', 0.7)

            updated_beliefs.append(belief_id)

    db.commit()

    logger.info(f"Resolved prediction #{prediction_id} as {status}, updated {len(updated_beliefs)} beliefs")

    return {
        'updated_beliefs': len(updated_beliefs),
        'belief_ids': updated_beliefs
    }


def check_expired_predictions(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Find predictions past their deadline that haven't been resolved.

    Args:
        db: Database connection

    Returns:
        List of expired prediction dictionaries
    """
    now = datetime.now().strftime('%Y-%m-%d')

    rows = db.execute("""
        SELECT * FROM predictions
        WHERE status = 'open'
        AND deadline IS NOT NULL
        AND deadline < ?
        ORDER BY deadline ASC
    """, (now,)).fetchall()

    return [dict(row) for row in rows]


# ----------------------------------------------------------------------------
# Contradiction Detection and Resolution
# ----------------------------------------------------------------------------

def detect_contradictions(db: sqlite3.Connection, statement: str) -> List[Dict[str, Any]]:
    """Check if a statement contradicts existing beliefs.

    Args:
        db: Database connection
        statement: The new statement to check

    Returns:
        List of conflicting belief dictionaries
    """
    # Get all active beliefs
    beliefs = db.execute("""
        SELECT id, statement, confidence, category
        FROM beliefs WHERE status = 'active'
    """).fetchall()

    conflicts = []

    # Negation patterns
    negation_patterns = [
        r'\bnot\b', r'\bdon\'?t\b', r'\bdoesn\'?t\b', r'\bdidn\'?t\b',
        r'\bwon\'?t\b', r'\bcannot\b', r'\bcan\'?t\b', r'\bnever\b',
        r'\bno\b', r'\bfalse\b', r'\bincorrect\b', r'\binvalid\b'
    ]

    statement_lower = statement.lower()
    has_negation_new = any(re.search(pat, statement_lower) for pat in negation_patterns)

    for belief in beliefs:
        # Check semantic similarity
        ratio = SequenceMatcher(None, statement_lower, belief['statement'].lower()).ratio()

        if ratio > 0.80:  # High similarity
            belief_lower = belief['statement'].lower()
            has_negation_existing = any(re.search(pat, belief_lower) for pat in negation_patterns)

            # If one has negation and the other doesn't = contradiction
            if has_negation_new != has_negation_existing:
                conflicts.append({
                    'belief_id': belief['id'],
                    'statement': belief['statement'],
                    'confidence': belief['confidence'],
                    'similarity': ratio,
                    'category': belief['category']
                })

    return conflicts


def resolve_contradiction(
    db: sqlite3.Connection,
    belief_id_keep: int,
    belief_id_discard: int
) -> None:
    """Resolve a contradiction by keeping one belief and discarding another.

    Args:
        db: Database connection
        belief_id_keep: ID of the belief to keep
        belief_id_discard: ID of the belief to discard
    """
    # Mark discarded belief as disproven
    db.execute("""
        UPDATE beliefs
        SET status = 'disproven', updated_at = datetime('now')
        WHERE id = ?
    """, (belief_id_discard,))

    # Log as evidence against the discarded belief
    db.execute("""
        INSERT INTO belief_revisions (belief_id, old_confidence, new_confidence, reason, revision_type)
        VALUES (?, (SELECT confidence FROM beliefs WHERE id = ?), 0.01,
                'Contradicted by belief #' || ?, 'contradiction')
    """, (belief_id_discard, belief_id_discard, belief_id_keep))

    # Set confidence to minimum
    db.execute("""
        UPDATE beliefs SET confidence = 0.01 WHERE id = ?
    """, (belief_id_discard,))

    db.commit()

    logger.info(f"Resolved contradiction: kept belief #{belief_id_keep}, discarded #{belief_id_discard}")


# ----------------------------------------------------------------------------
# Belief Decay (Extended System)
# ----------------------------------------------------------------------------

def decay_beliefs(db: sqlite3.Connection, days_inactive: int = 90) -> int:
    """Decay confidence of inactive or unsupported beliefs.

    Args:
        db: Database connection
        days_inactive: Number of days of inactivity before decay (default 90)

    Returns:
        Number of beliefs decayed
    """
    cutoff_date = (datetime.now() - timedelta(days=days_inactive)).strftime('%Y-%m-%d')

    # Find beliefs that:
    # 1. Haven't been updated recently
    # 2. Have no supporting evidence OR low evidence count
    # 3. Are not confirmed status

    candidates = db.execute("""
        SELECT id, confidence, evidence_for, evidence_against, status
        FROM beliefs
        WHERE status = 'active'
        AND updated_at < ?
        AND confidence > 0.2
    """, (cutoff_date,)).fetchall()

    decayed_count = 0

    for belief in candidates:
        # Faster decay for beliefs with no evidence
        if belief['evidence_for'] == 0 and belief['evidence_against'] == 0:
            decay_amount = 0.20  # 20% reduction
        else:
            decay_amount = 0.10  # 10% reduction

        new_conf = max(0.01, belief['confidence'] * (1 - decay_amount))

        update_belief_confidence(
            db, belief['id'], new_conf,
            f"Decay due to {days_inactive}+ days inactivity",
            revision_type='decay'
        )

        decayed_count += 1

    db.commit()

    logger.info(f"Decayed {decayed_count} beliefs")
    return decayed_count


# ----------------------------------------------------------------------------
# Analytics and Statistics
# ----------------------------------------------------------------------------

def belief_accuracy(db: sqlite3.Connection) -> Dict[str, Any]:
    """Calculate accuracy statistics for predictions.

    Returns:
        Dictionary with accuracy and calibration metrics
    """
    # Get all resolved predictions
    predictions = db.execute("""
        SELECT confidence, status FROM predictions
        WHERE status IN ('confirmed', 'refuted')
    """).fetchall()

    if not predictions:
        return {
            'total_predictions': 0,
            'correct_count': 0,
            'correct_percentage': 0.0,
            'avg_confidence_correct': 0.0,
            'avg_confidence_incorrect': 0.0,
            'calibration': {}
        }

    total = len(predictions)
    correct = sum(1 for p in predictions if p['status'] == 'confirmed')
    incorrect = total - correct

    # Average confidence for correct vs incorrect
    conf_correct = [p['confidence'] for p in predictions if p['status'] == 'confirmed']
    conf_incorrect = [p['confidence'] for p in predictions if p['status'] == 'refuted']

    avg_conf_correct = sum(conf_correct) / len(conf_correct) if conf_correct else 0.0
    avg_conf_incorrect = sum(conf_incorrect) / len(conf_incorrect) if conf_incorrect else 0.0

    # Calibration: bucket predictions by confidence and check accuracy in each bucket
    calibration = {}
    buckets = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0)]

    for low, high in buckets:
        bucket_preds = [p for p in predictions if low <= p['confidence'] < high]
        if bucket_preds:
            bucket_correct = sum(1 for p in bucket_preds if p['status'] == 'confirmed')
            bucket_accuracy = bucket_correct / len(bucket_preds)
            calibration[f"{int(low*100)}-{int(high*100)}%"] = {
                'count': len(bucket_preds),
                'accuracy': bucket_accuracy,
                'expected': (low + high) / 2,
                'calibration_error': abs(bucket_accuracy - (low + high) / 2)
            }

    return {
        'total_predictions': total,
        'correct_count': correct,
        'incorrect_count': incorrect,
        'correct_percentage': correct / total * 100,
        'avg_confidence_correct': avg_conf_correct,
        'avg_confidence_incorrect': avg_conf_incorrect,
        'calibration': calibration
    }


def strongest_beliefs_extended(db: sqlite3.Connection, n: int = 10) -> List[Dict[str, Any]]:
    """Get the N strongest (highest confidence) beliefs (extended system).

    Args:
        db: Database connection
        n: Number of beliefs to return

    Returns:
        List of belief dictionaries
    """
    rows = db.execute("""
        SELECT * FROM beliefs
        WHERE status = 'active'
        ORDER BY confidence DESC, evidence_for DESC
        LIMIT ?
    """, (n,)).fetchall()

    return [dict(row) for row in rows]


def weakest_beliefs_extended(db: sqlite3.Connection, n: int = 10) -> List[Dict[str, Any]]:
    """Get the N weakest (lowest confidence) beliefs (extended system).

    Args:
        db: Database connection
        n: Number of beliefs to return

    Returns:
        List of belief dictionaries
    """
    rows = db.execute("""
        SELECT * FROM beliefs
        WHERE status = 'active'
        ORDER BY confidence ASC, evidence_against DESC
        LIMIT ?
    """, (n,)).fetchall()

    return [dict(row) for row in rows]


def most_revised(db: sqlite3.Connection, n: int = 10) -> List[Dict[str, Any]]:
    """Get beliefs with the most revisions (most controversial/uncertain).

    Args:
        db: Database connection
        n: Number of beliefs to return

    Returns:
        List of belief dictionaries with revision counts
    """
    rows = db.execute("""
        SELECT b.*, COUNT(br.id) as revision_count
        FROM beliefs b
        LEFT JOIN belief_revisions br ON b.id = br.belief_id
        WHERE b.status = 'active'
        GROUP BY b.id
        ORDER BY revision_count DESC, b.updated_at DESC
        LIMIT ?
    """, (n,)).fetchall()

    return [dict(row) for row in rows]


# ----------------------------------------------------------------------------
# Truth Lifecycle States
# ----------------------------------------------------------------------------

def set_belief_state(
    db: sqlite3.Connection,
    belief_id: int,
    new_state: str,
    reason: Optional[str] = None
) -> None:
    """Transition a belief to a new lifecycle state.

    Args:
        db: Database connection
        belief_id: ID of the belief
        new_state: New state (hypothesis/tested/validated/deprecated/refuted)
        reason: Optional reason for the transition
    """
    valid_states = ['hypothesis', 'tested', 'validated', 'deprecated', 'refuted']
    if new_state not in valid_states:
        raise ValueError(f"Invalid state: {new_state}. Must be one of {valid_states}")

    # Get current state
    row = db.execute("SELECT belief_state, confidence FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
    if not row:
        logger.warning(f"Belief #{belief_id} not found")
        return

    old_state = row['belief_state'] or 'hypothesis'

    # Update state
    db.execute("""
        UPDATE beliefs
        SET belief_state = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (new_state, belief_id))

    # Log as a revision
    reason_text = reason or f"State transition: {old_state} → {new_state}"
    db.execute("""
        INSERT INTO belief_revisions (belief_id, old_confidence, new_confidence, reason, revision_type)
        VALUES (?, ?, ?, ?, 'lifecycle')
    """, (belief_id, row['confidence'], row['confidence'], reason_text))

    db.commit()

    logger.info(f"Belief #{belief_id} state: {old_state} → {new_state}")


def get_belief_state(db: sqlite3.Connection, belief_id: int) -> str:
    """Get the current lifecycle state of a belief.

    Args:
        db: Database connection
        belief_id: ID of the belief

    Returns:
        Current state (hypothesis/tested/validated/deprecated/refuted)
    """
    row = db.execute("SELECT belief_state FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
    if not row:
        return 'hypothesis'  # Default
    return row['belief_state'] or 'hypothesis'


def list_beliefs_by_state(
    db: sqlite3.Connection,
    state: str,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List beliefs filtered by lifecycle state.

    Args:
        db: Database connection
        state: Lifecycle state to filter by
        category: Optional category filter

    Returns:
        List of belief dictionaries
    """
    query = "SELECT * FROM beliefs WHERE belief_state = ? AND status = 'active'"
    params: List[Any] = [state]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY confidence DESC, updated_at DESC"

    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def auto_transition_on_prediction(
    db: sqlite3.Connection,
    prediction_id: int,
    confirmed: bool
) -> List[int]:
    """Auto-transition belief states when predictions are resolved.

    Args:
        db: Database connection
        prediction_id: ID of the resolved prediction
        confirmed: True if prediction was confirmed, False if refuted

    Returns:
        List of belief IDs that were transitioned
    """
    # Get prediction details
    pred = db.execute("""
        SELECT memory_id FROM predictions WHERE id = ?
    """, (prediction_id,)).fetchone()

    if not pred or not pred['memory_id']:
        return []

    # Find beliefs linked to this memory
    beliefs = db.execute("""
        SELECT id, belief_state FROM beliefs
        WHERE memory_id = ? AND status = 'active'
    """, (pred['memory_id'],)).fetchall()

    transitioned = []

    for belief_row in beliefs:
        belief_id = belief_row['id']
        current_state = belief_row['belief_state'] or 'hypothesis'

        if confirmed:
            # Prediction confirmed → move to 'validated' (if not already)
            if current_state in ('hypothesis', 'tested'):
                set_belief_state(
                    db, belief_id, 'validated',
                    f"Prediction #{prediction_id} confirmed"
                )
                transitioned.append(belief_id)
        else:
            # Prediction refuted → move to 'refuted'
            if current_state != 'refuted':
                set_belief_state(
                    db, belief_id, 'refuted',
                    f"Prediction #{prediction_id} refuted"
                )
                transitioned.append(belief_id)

    return transitioned


def auto_deprecate_weak_beliefs(db: sqlite3.Connection, days_inactive: int = 60) -> int:
    """Auto-deprecate beliefs with low confidence that haven't been accessed recently.

    Called during dream mode to clean up weak, stale beliefs.

    Args:
        db: Database connection
        days_inactive: Days of inactivity before deprecation (default 60)

    Returns:
        Number of beliefs deprecated
    """
    cutoff_date = (datetime.now() - timedelta(days=days_inactive)).strftime('%Y-%m-%d')

    # Find beliefs that are:
    # 1. Low confidence (< 0.2)
    # 2. Not accessed recently (or never accessed)
    # 3. Not already deprecated or refuted
    # 4. Not immune (access_count < 5 on linked memory)

    candidates = db.execute("""
        SELECT b.id, b.memory_id, b.confidence, b.belief_state
        FROM beliefs b
        LEFT JOIN memories m ON b.memory_id = m.id
        WHERE b.status = 'active'
        AND b.belief_state NOT IN ('deprecated', 'refuted', 'validated')
        AND b.confidence < 0.2
        AND b.updated_at < ?
        AND (m.access_count IS NULL OR m.access_count < 5)
    """, (cutoff_date,)).fetchall()

    deprecated_count = 0

    for belief in candidates:
        set_belief_state(
            db, belief['id'], 'deprecated',
            f"Auto-deprecated: low confidence ({belief['confidence']:.2f}) + {days_inactive}+ days inactive"
        )
        deprecated_count += 1

    if deprecated_count > 0:
        logger.info(f"Auto-deprecated {deprecated_count} weak beliefs")

    return deprecated_count


# ----------------------------------------------------------------------------
# Temporal Timeline View
# ----------------------------------------------------------------------------

def log_confidence_change(
    db: sqlite3.Connection,
    belief_id: Optional[int] = None,
    memory_id: Optional[int] = None,
    old_confidence: float = 0.0,
    new_confidence: float = 0.0,
    reason: str = "",
    source_type: str = "manual"
) -> None:
    """Log a confidence change to the timeline.

    Args:
        db: Database connection
        belief_id: ID of the belief (optional)
        memory_id: ID of the memory (optional)
        old_confidence: Previous confidence value
        new_confidence: New confidence value
        reason: Reason for the change
        source_type: Type of change source (manual/prediction/evidence/decay)
    """
    db.execute("""
        INSERT INTO belief_timeline (belief_id, memory_id, old_confidence, new_confidence, reason, source_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (belief_id, memory_id, old_confidence, new_confidence, reason, source_type))
    db.commit()


def get_timeline(
    db: sqlite3.Connection,
    belief_id: Optional[int] = None,
    memory_id: Optional[int] = None,
    project: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Get timeline of belief/confidence changes.

    Args:
        db: Database connection
        belief_id: Filter by specific belief ID (optional)
        memory_id: Filter by specific memory ID (optional)
        project: Filter by project (optional)
        days: Number of days to look back (default 30)

    Returns:
        List of timeline entries with confidence changes
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    query = """
        SELECT
            t.*,
            b.statement as belief_statement,
            m.content as memory_content,
            m.category as memory_category,
            m.project as memory_project
        FROM belief_timeline t
        LEFT JOIN beliefs b ON t.belief_id = b.id
        LEFT JOIN memories m ON t.memory_id = m.id
        WHERE t.timestamp >= ?
    """
    params = [cutoff_date]

    if belief_id:
        query += " AND t.belief_id = ?"
        params.append(belief_id)

    if memory_id:
        query += " AND t.memory_id = ?"
        params.append(memory_id)

    if project:
        query += " AND m.project = ?"
        params.append(project)

    query += " ORDER BY t.timestamp DESC"

    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_confidence_history(db: sqlite3.Connection, identifier: int, is_belief: bool = True) -> List[Dict[str, Any]]:
    """Get full confidence history for a belief or memory.

    Args:
        db: Database connection
        identifier: Belief ID or memory ID
        is_belief: True if identifier is a belief ID, False if memory ID

    Returns:
        List of confidence changes over time
    """
    if is_belief:
        # Get history from belief_timeline and belief_revisions
        timeline_entries = db.execute("""
            SELECT
                timestamp as time,
                old_confidence,
                new_confidence,
                reason,
                source_type,
                'timeline' as source_table
            FROM belief_timeline
            WHERE belief_id = ?
            ORDER BY timestamp ASC
        """, (identifier,)).fetchall()

        revision_entries = db.execute("""
            SELECT
                created_at as time,
                old_confidence,
                new_confidence,
                reason,
                revision_type as source_type,
                'revisions' as source_table
            FROM belief_revisions
            WHERE belief_id = ?
            ORDER BY created_at ASC
        """, (identifier,)).fetchall()

        # Merge and sort by time
        all_entries = list(timeline_entries) + list(revision_entries)
        all_entries.sort(key=lambda x: x['time'])

        return [dict(entry) for entry in all_entries]
    else:
        # Get history from belief_updates (for memories)
        entries = db.execute("""
            SELECT
                updated_at as time,
                old_confidence,
                new_confidence,
                reason,
                'memory' as source_type,
                'belief_updates' as source_table
            FROM belief_updates
            WHERE memory_id = ?
            ORDER BY updated_at ASC
        """, (identifier,)).fetchall()

        # Also get from timeline
        timeline_entries = db.execute("""
            SELECT
                timestamp as time,
                old_confidence,
                new_confidence,
                reason,
                source_type,
                'timeline' as source_table
            FROM belief_timeline
            WHERE memory_id = ?
            ORDER BY timestamp ASC
        """, (identifier,)).fetchall()

        # Merge and sort
        all_entries = list(entries) + list(timeline_entries)
        all_entries.sort(key=lambda x: x['time'])

        return [dict(entry) for entry in all_entries]


def format_timeline_entry(entry: Dict[str, Any]) -> str:
    """Format a timeline entry for display.

    Args:
        entry: Timeline entry dictionary

    Returns:
        Formatted string with arrows showing direction
    """
    old_conf = entry['old_confidence']
    new_conf = entry['new_confidence']

    # Determine arrow direction
    if new_conf > old_conf:
        arrow = "↑"
    elif new_conf < old_conf:
        arrow = "↓"
    else:
        arrow = "→"

    timestamp = entry['timestamp'][:16] if 'timestamp' in entry else entry.get('time', '')[:16]
    reason = entry.get('reason', 'No reason')
    source_type = entry.get('source_type', 'unknown')

    # Format confidence change
    conf_change = f"{old_conf:.2f} {arrow} {new_conf:.2f}"

    return f"[{timestamp}] {conf_change} ({source_type}): {reason[:60]}"


def get_timeline_summary(db: sqlite3.Connection, days: int = 7) -> Dict[str, Any]:
    """Get summary statistics for timeline over recent days.

    Args:
        db: Database connection
        days: Number of days to analyze (default 7)

    Returns:
        Dictionary with summary stats
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    stats = {}

    # Total changes
    total = db.execute("""
        SELECT COUNT(*) as count FROM belief_timeline WHERE timestamp >= ?
    """, (cutoff_date,)).fetchone()
    stats['total_changes'] = total['count']

    # Increases vs decreases
    increases = db.execute("""
        SELECT COUNT(*) as count FROM belief_timeline
        WHERE timestamp >= ? AND new_confidence > old_confidence
    """, (cutoff_date,)).fetchone()
    stats['increases'] = increases['count']

    decreases = db.execute("""
        SELECT COUNT(*) as count FROM belief_timeline
        WHERE timestamp >= ? AND new_confidence < old_confidence
    """, (cutoff_date,)).fetchone()
    stats['decreases'] = decreases['count']

    # By source type
    by_source = db.execute("""
        SELECT source_type, COUNT(*) as count
        FROM belief_timeline
        WHERE timestamp >= ?
        GROUP BY source_type
        ORDER BY count DESC
    """, (cutoff_date,)).fetchall()
    stats['by_source'] = [dict(row) for row in by_source]

    # Average confidence change
    avg_change = db.execute("""
        SELECT AVG(new_confidence - old_confidence) as avg_delta
        FROM belief_timeline
        WHERE timestamp >= ?
    """, (cutoff_date,)).fetchone()
    stats['avg_confidence_delta'] = avg_change['avg_delta'] or 0.0

    return stats


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# These aliases maintain backward compatibility with existing code
# that imports from beliefs.py expecting simple system functions

# Simple system (default)
resolve_prediction = resolve_prediction_memory
strongest_beliefs = strongest_beliefs_memory
weakest_beliefs = weakest_beliefs_memory
