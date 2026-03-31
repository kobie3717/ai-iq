"""Extended belief and prediction system with evidence tracking and Bayesian updates.

This module extends the basic beliefs.py with:
- Explicit beliefs table (separate from memories)
- Evidence tracking with support/contradict directions
- Sophisticated Bayesian confidence updates
- Belief accuracy and calibration statistics
- Enhanced contradiction detection and resolution

The basic beliefs.py uses memories.confidence directly.
This module adds a layer on top for explicit beliefs with evidence.
"""

import sqlite3
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from difflib import SequenceMatcher

from .database import get_db
from .config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Database Schema Migration
# ============================================================================

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
            status TEXT DEFAULT 'active'
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


# ============================================================================
# Belief CRUD Operations
# ============================================================================

def add_belief(
    db: sqlite3.Connection,
    statement: str,
    confidence: float = 0.5,
    category: str = 'general',
    source: str = 'user',
    memory_id: Optional[int] = None
) -> int:
    """Add a new belief to the system.

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


# ============================================================================
# Bayesian Confidence Updates with Evidence
# ============================================================================

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


# ============================================================================
# Prediction Integration (extends existing predictions table)
# ============================================================================

def make_prediction(
    db: sqlite3.Connection,
    belief_id: int,
    prediction_text: str,
    confidence: Optional[float] = None,
    deadline: Optional[str] = None
) -> int:
    """Make a prediction based on a belief.

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


def resolve_prediction(
    db: sqlite3.Connection,
    prediction_id: int,
    outcome: str,
    correct: bool
) -> Dict[str, Any]:
    """Resolve a prediction and update related beliefs.

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
                new_conf = bayesian_update(db, belief_id, 'supports', 0.7)
            else:
                # Weaken belief confidence
                new_conf = bayesian_update(db, belief_id, 'contradicts', 0.7)

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


# ============================================================================
# Contradiction Detection and Resolution
# ============================================================================

def detect_contradictions(db: sqlite3.Connection, statement: str) -> List[Dict[str, Any]]:
    """Check if a statement contradicts existing beliefs.

    Args:
        db: Database connection
        statement: The new statement to check

    Returns:
        List of conflicting belief dictionaries
    """
    import re

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


# ============================================================================
# Belief Decay
# ============================================================================

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


# ============================================================================
# Analytics and Statistics
# ============================================================================

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


def strongest_beliefs(db: sqlite3.Connection, n: int = 10) -> List[Dict[str, Any]]:
    """Get the N strongest (highest confidence) beliefs.

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


def weakest_beliefs(db: sqlite3.Connection, n: int = 10) -> List[Dict[str, Any]]:
    """Get the N weakest (lowest confidence) beliefs.

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


# ============================================================================
# Truth Lifecycle States (Feature 1)
# ============================================================================

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


# ============================================================================
# Temporal Timeline View (Feature 2)
# ============================================================================

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
        color_code = "32"  # Green (ANSI)
    elif new_conf < old_conf:
        arrow = "↓"
        color_code = "31"  # Red (ANSI)
    else:
        arrow = "→"
        color_code = "33"  # Yellow (ANSI)

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
