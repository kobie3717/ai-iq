"""ReasoningBank-inspired retrieval boost.

Successful reasoning trajectories (memories linked to confirmed predictions)
rank higher on retrieval. Inspired by ruvnet/ruflo's ReasoningBank pattern.

A memory's reasoning_score is derived from the outcomes of predictions it's
linked to via the derived_from field or the predictions.memory_id foreign key.
"""

import sqlite3
from typing import Dict, Tuple, Optional, List
from .config import get_logger

logger = get_logger(__name__)


def compute_reasoning_score(db: sqlite3.Connection, memory_id: int) -> Tuple[float, Dict]:
    """Compute reasoning score for a memory based on prediction outcomes.

    Args:
        db: Database connection
        memory_id: ID of the memory

    Returns:
        Tuple of (reasoning_score, details_dict) where:
        - reasoning_score: 0.0-1.0, where 0.5 is neutral, >0.5 is positive, <0.5 is negative
        - details_dict: {'confirmed': N, 'refuted': M, 'open': K, 'predictions': [...]}
    """
    # Find predictions where this memory is the source (memory_id field)
    predictions = db.execute("""
        SELECT id, prediction, status, confidence, expected_outcome, actual_outcome
        FROM predictions
        WHERE memory_id = ?
    """, (memory_id,)).fetchall()

    # Also find predictions that list this memory in their derived_from chain
    # The derived_from field is a comma-separated list of memory IDs
    derived_predictions = db.execute("""
        SELECT p.id, p.prediction, p.status, p.confidence, p.expected_outcome, p.actual_outcome
        FROM predictions p
        JOIN memories m ON p.memory_id = m.id
        WHERE m.derived_from LIKE ? OR m.derived_from LIKE ? OR m.derived_from = ?
    """, (f"%,{memory_id},%", f"%,{memory_id}", str(memory_id))).fetchall()

    # Combine both sets
    all_predictions = list(predictions) + list(derived_predictions)
    if not all_predictions:
        return 0.5, {'confirmed': 0, 'refuted': 0, 'open': 0, 'predictions': []}

    confirmed = 0
    refuted = 0
    open_count = 0
    prediction_details = []

    for pred in all_predictions:
        status = pred['status']
        prediction_details.append({
            'id': pred['id'],
            'prediction': pred['prediction'],
            'status': status,
            'confidence': pred['confidence'],
            'expected': pred['expected_outcome'],
            'actual': pred['actual_outcome']
        })

        if status == 'confirmed':
            confirmed += 1
        elif status == 'refuted':
            refuted += 1
        else:  # open, expired, etc.
            open_count += 1

    # Calculate reasoning score
    # confirmed predictions boost the score, refuted predictions lower it
    # open predictions are neutral (we don't know yet)
    total_resolved = confirmed + refuted
    if total_resolved == 0:
        # No resolved predictions yet → neutral
        reasoning_score = 0.5
    else:
        # Ratio of confirmed to total resolved
        reasoning_score = confirmed / total_resolved

    details = {
        'confirmed': confirmed,
        'refuted': refuted,
        'open': open_count,
        'predictions': prediction_details
    }

    return reasoning_score, details


def compute_reasoning_boost(reasoning_score: float) -> float:
    """Convert reasoning score to a retrieval boost multiplier.

    Args:
        reasoning_score: 0.0-1.0 (from compute_reasoning_score)

    Returns:
        Multiplier between 0.7 and 1.5
        - 1.0 = neutral (reasoning_score = 0.5)
        - 1.5 = max boost (reasoning_score = 1.0, all predictions confirmed)
        - 0.7 = max penalty (reasoning_score = 0.0, all predictions refuted)
    """
    # Linear mapping: score 0.5 → boost 1.0, score 1.0 → boost 1.5, score 0.0 → boost 0.7
    # Formula: boost = 1.0 + (score - 0.5) * 1.0
    boost = 1.0 + (reasoning_score - 0.5) * 1.0
    # Clamp to safe range
    return max(0.7, min(1.5, boost))


def get_reasoning_boosts(db: sqlite3.Connection, memory_ids: List[int]) -> Dict[int, float]:
    """Batch compute reasoning boosts for multiple memories.

    Args:
        db: Database connection
        memory_ids: List of memory IDs

    Returns:
        Dictionary mapping memory_id → reasoning_boost (multiplicative factor)
    """
    boosts = {}
    for mem_id in memory_ids:
        score, _ = compute_reasoning_score(db, mem_id)
        boosts[mem_id] = compute_reasoning_boost(score)
    return boosts


def show_reasoning_details(db: sqlite3.Connection, memory_id: int) -> str:
    """Generate a human-readable report of a memory's reasoning score.

    Args:
        db: Database connection
        memory_id: ID of the memory

    Returns:
        Formatted string with reasoning details
    """
    # Get memory content
    mem = db.execute("SELECT content, category, project FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not mem:
        return f"Memory #{memory_id} not found"

    score, details = compute_reasoning_score(db, memory_id)
    boost = compute_reasoning_boost(score)

    lines = []
    lines.append(f"Memory #{memory_id}")
    lines.append(f"Content: {mem['content'][:100]}{'...' if len(mem['content']) > 100 else ''}")
    lines.append(f"Category: {mem['category']} | Project: {mem['project'] or 'N/A'}")
    lines.append("")
    lines.append(f"Reasoning Score: {score:.2f} (0.0=all refuted, 0.5=neutral, 1.0=all confirmed)")
    lines.append(f"Retrieval Boost: {boost:.2f}x (0.7x min, 1.0x neutral, 1.5x max)")
    lines.append("")

    if details['predictions']:
        lines.append(f"Linked Predictions: {details['confirmed']} confirmed, {details['refuted']} refuted, {details['open']} open")
        lines.append("")
        for pred in details['predictions']:
            status_symbol = "✓" if pred['status'] == 'confirmed' else "✗" if pred['status'] == 'refuted' else "○"
            lines.append(f"  {status_symbol} Prediction #{pred['id']} [{pred['status']}] (conf: {pred['confidence']:.2f})")
            lines.append(f"    {pred['prediction'][:80]}{'...' if len(pred['prediction']) > 80 else ''}")
            if pred['expected']:
                lines.append(f"    Expected: {pred['expected'][:60]}{'...' if len(pred['expected']) > 60 else ''}")
            if pred['actual']:
                lines.append(f"    Actual: {pred['actual'][:60]}{'...' if len(pred['actual']) > 60 else ''}")
    else:
        lines.append("No linked predictions found → neutral score (1.0x boost)")

    return "\n".join(lines)


def get_top_reasoning_memories(db: sqlite3.Connection, limit: int = 10) -> List[Tuple[int, float, float, Dict]]:
    """Get top memories by reasoning boost score.

    Args:
        db: Database connection
        limit: Number of top memories to return

    Returns:
        List of tuples: (memory_id, reasoning_score, reasoning_boost, details)
        Sorted by boost (highest first)
    """
    # Get all active memories
    rows = db.execute("SELECT id FROM memories WHERE active = 1").fetchall()

    # Compute reasoning score and boost for each
    scored_memories = []
    for row in rows:
        mem_id = row['id']
        score, details = compute_reasoning_score(db, mem_id)
        # Only include memories with predictions (confirmed or refuted)
        if details['confirmed'] > 0 or details['refuted'] > 0:
            boost = compute_reasoning_boost(score)
            scored_memories.append((mem_id, score, boost, details))

    # Sort by boost descending
    scored_memories.sort(key=lambda x: -x[2])

    return scored_memories[:limit]


def get_reasoning_statistics(db: sqlite3.Connection) -> Dict[str, int]:
    """Get statistics about reasoning boosts across all memories.

    Args:
        db: Database connection

    Returns:
        Dictionary with counts of boosted/penalized/neutral memories
    """
    rows = db.execute("SELECT id FROM memories WHERE active = 1").fetchall()

    boosted = 0  # boost > 1.0
    penalized = 0  # boost < 1.0
    neutral = 0  # boost = 1.0
    total_with_predictions = 0

    for row in rows:
        mem_id = row['id']
        score, details = compute_reasoning_score(db, mem_id)
        if details['confirmed'] > 0 or details['refuted'] > 0:
            total_with_predictions += 1
            boost = compute_reasoning_boost(score)
            if boost > 1.0:
                boosted += 1
            elif boost < 1.0:
                penalized += 1
            else:
                neutral += 1

    return {
        'boosted': boosted,
        'penalized': penalized,
        'neutral': neutral,
        'total_with_predictions': total_with_predictions
    }
