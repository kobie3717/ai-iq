"""Meta-Learning — auto-tunes search weights based on usage patterns.

Tracks which search modes produce results that users actually use,
then adjusts RRF fusion weights to improve retrieval quality over time.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from .database import get_db
from .config import get_logger, DB_PATH
from pathlib import Path

logger = get_logger(__name__)

# Default weights for RRF fusion
DEFAULT_WEIGHTS = {
    'keyword_weight': 1.0,
    'semantic_weight': 1.0,
    'recency_bonus': 0.1,
    'confidence_bonus': 0.05,
    'access_bonus': 0.02,
}

# Meta-learning config stored alongside DB
META_CONFIG_PATH = DB_PATH.parent / "meta_weights.json"


def init_meta_tables(db: sqlite3.Connection) -> None:
    """Create meta-learning tracking tables."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS meta_search_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER,
            query TEXT NOT NULL,
            search_mode TEXT DEFAULT 'hybrid',
            keyword_results INTEGER DEFAULT 0,
            semantic_results INTEGER DEFAULT 0,
            used_from_keyword INTEGER DEFAULT 0,
            used_from_semantic INTEGER DEFAULT 0,
            total_results INTEGER DEFAULT 0,
            total_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS meta_weight_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weights TEXT NOT NULL,
            reason TEXT,
            keyword_effectiveness REAL,
            semantic_effectiveness REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_meta_outcomes_created ON meta_search_outcomes(created_at);
        CREATE INDEX IF NOT EXISTS idx_meta_outcomes_mode ON meta_search_outcomes(search_mode);
    """)
    db.commit()


def get_current_weights() -> Dict[str, float]:
    """Load current search weights from config file.

    Returns:
        Dict of weight name → value
    """
    if META_CONFIG_PATH.exists():
        try:
            with open(META_CONFIG_PATH) as f:
                weights = json.load(f)
            # Ensure all keys present
            for k, v in DEFAULT_WEIGHTS.items():
                if k not in weights:
                    weights[k] = v
            return weights
        except (json.JSONDecodeError, IOError):
            pass

    return dict(DEFAULT_WEIGHTS)


def save_weights(weights: Dict[str, float], reason: str = "manual") -> None:
    """Save weights to config and log history.

    Args:
        weights: Dict of weight name → value
        reason: Why weights changed
    """
    with open(META_CONFIG_PATH, 'w') as f:
        json.dump(weights, f, indent=2)

    db = get_db()
    init_meta_tables(db)
    db.execute("""
        INSERT INTO meta_weight_history (weights, reason)
        VALUES (?, ?)
    """, (json.dumps(weights), reason))
    db.commit()
    db.close()

    logger.info(f"Saved weights: {weights} (reason: {reason})")


def log_search_outcome(
    db: sqlite3.Connection,
    search_id: int,
    query: str,
    search_mode: str,
    keyword_results: int,
    semantic_results: int,
    used_from_keyword: int,
    used_from_semantic: int
) -> None:
    """Log a search outcome for meta-learning analysis.

    Args:
        db: Database connection
        search_id: ID from search_log
        query: Search query
        search_mode: hybrid/keyword/semantic
        keyword_results: Number of results from keyword search
        semantic_results: Number of results from semantic search
        used_from_keyword: How many keyword results were actually used
        used_from_semantic: How many semantic results were actually used
    """
    init_meta_tables(db)
    db.execute("""
        INSERT INTO meta_search_outcomes
        (search_id, query, search_mode, keyword_results, semantic_results,
         used_from_keyword, used_from_semantic, total_results, total_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        search_id, query, search_mode,
        keyword_results, semantic_results,
        used_from_keyword, used_from_semantic,
        keyword_results + semantic_results,
        used_from_keyword + used_from_semantic
    ))
    db.commit()


def calculate_effectiveness(db: sqlite3.Connection, days: int = 30) -> Dict[str, Any]:
    """Calculate search mode effectiveness over a time period.

    Args:
        db: Database connection
        days: Number of days to analyze

    Returns:
        Dict with effectiveness stats per mode
    """
    init_meta_tables(db)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # Overall stats
    stats = db.execute("""
        SELECT
            COUNT(*) as total_searches,
            SUM(keyword_results) as total_keyword_results,
            SUM(semantic_results) as total_semantic_results,
            SUM(used_from_keyword) as total_keyword_used,
            SUM(used_from_semantic) as total_semantic_used,
            SUM(total_used) as total_used,
            SUM(total_results) as total_results
        FROM meta_search_outcomes
        WHERE created_at > ?
    """, (cutoff,)).fetchone()

    if not stats or stats['total_searches'] == 0:
        return {
            'total_searches': 0,
            'keyword_effectiveness': 0.5,
            'semantic_effectiveness': 0.5,
            'overall_hit_rate': 0.0,
            'recommendation': 'insufficient_data',
            'suggested_weights': get_current_weights()
        }

    total_keyword = stats['total_keyword_results'] or 0
    total_semantic = stats['total_semantic_results'] or 0
    used_keyword = stats['total_keyword_used'] or 0
    used_semantic = stats['total_semantic_used'] or 0

    # Calculate effectiveness (used / retrieved ratio)
    keyword_eff = used_keyword / total_keyword if total_keyword > 0 else 0.5
    semantic_eff = used_semantic / total_semantic if total_semantic > 0 else 0.5

    overall_hit_rate = (stats['total_used'] or 0) / stats['total_results'] if stats['total_results'] > 0 else 0.0

    # Suggest weight adjustments
    current = get_current_weights()
    suggested = dict(current)

    # Adjust weights proportionally to effectiveness
    if keyword_eff + semantic_eff > 0:
        ratio = keyword_eff / (keyword_eff + semantic_eff)
        # Nudge weights toward the more effective mode (slow learning rate)
        learning_rate = 0.1
        target_keyword = 0.5 + (ratio - 0.5) * 2  # Scale to 0-1 range
        suggested['keyword_weight'] = current['keyword_weight'] + learning_rate * (target_keyword - current['keyword_weight'] / (current['keyword_weight'] + current['semantic_weight']))
        suggested['semantic_weight'] = current['semantic_weight'] + learning_rate * ((1 - target_keyword) - current['semantic_weight'] / (current['keyword_weight'] + current['semantic_weight']))

        # Clamp to reasonable bounds
        suggested['keyword_weight'] = max(0.3, min(2.0, suggested['keyword_weight']))
        suggested['semantic_weight'] = max(0.3, min(2.0, suggested['semantic_weight']))

    # Determine recommendation
    if stats['total_searches'] < 10:
        recommendation = 'insufficient_data'
    elif keyword_eff > semantic_eff * 1.5:
        recommendation = 'boost_keyword'
    elif semantic_eff > keyword_eff * 1.5:
        recommendation = 'boost_semantic'
    else:
        recommendation = 'balanced'

    return {
        'total_searches': stats['total_searches'],
        'keyword_effectiveness': keyword_eff,
        'semantic_effectiveness': semantic_eff,
        'keyword_stats': {'retrieved': total_keyword, 'used': used_keyword},
        'semantic_stats': {'retrieved': total_semantic, 'used': used_semantic},
        'overall_hit_rate': overall_hit_rate,
        'recommendation': recommendation,
        'current_weights': current,
        'suggested_weights': suggested
    }


def apply_learned_weights(db: sqlite3.Connection, min_searches: int = 20) -> Dict[str, Any]:
    """Apply learned search weights based on accumulated feedback.

    Only applies if enough data has been collected.

    Args:
        db: Database connection
        min_searches: Minimum searches required before adjusting

    Returns:
        Dict with what was done
    """
    stats = calculate_effectiveness(db, days=30)

    if stats['total_searches'] < min_searches:
        return {
            'applied': False,
            'reason': f"Need {min_searches} searches, have {stats['total_searches']}",
            'stats': stats
        }

    if stats['recommendation'] == 'balanced':
        return {
            'applied': False,
            'reason': 'Search modes are already balanced',
            'stats': stats
        }

    # Apply suggested weights
    old_weights = get_current_weights()
    new_weights = stats['suggested_weights']

    # Only apply if change is significant
    keyword_delta = abs(new_weights['keyword_weight'] - old_weights['keyword_weight'])
    semantic_delta = abs(new_weights['semantic_weight'] - old_weights['semantic_weight'])

    if keyword_delta < 0.05 and semantic_delta < 0.05:
        return {
            'applied': False,
            'reason': 'Changes too small to apply',
            'stats': stats
        }

    save_weights(new_weights, reason=f"meta-learning: {stats['recommendation']}")

    return {
        'applied': True,
        'old_weights': old_weights,
        'new_weights': new_weights,
        'recommendation': stats['recommendation'],
        'stats': stats
    }


def get_weight_history(db: sqlite3.Connection, limit: int = 20) -> List[Dict[str, Any]]:
    """Get history of weight changes.

    Args:
        db: Database connection
        limit: Max entries to return

    Returns:
        List of weight change records
    """
    init_meta_tables(db)
    rows = db.execute("""
        SELECT * FROM meta_weight_history
        ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()

    results = []
    for row in rows:
        entry = dict(row)
        try:
            entry['weights'] = json.loads(entry['weights'])
        except (json.JSONDecodeError, TypeError):
            pass
        results.append(entry)

    return results


def get_meta_stats(db: sqlite3.Connection) -> Dict[str, Any]:
    """Get comprehensive meta-learning statistics.

    Args:
        db: Database connection

    Returns:
        Dict with all meta-learning stats
    """
    init_meta_tables(db)

    # Current weights
    weights = get_current_weights()

    # Effectiveness over different periods
    eff_7d = calculate_effectiveness(db, days=7)
    eff_30d = calculate_effectiveness(db, days=30)
    eff_all = calculate_effectiveness(db, days=3650)

    # Weight change count
    weight_changes = db.execute(
        "SELECT COUNT(*) as c FROM meta_weight_history"
    ).fetchone()['c']

    # Search mode distribution
    mode_dist = db.execute("""
        SELECT search_mode, COUNT(*) as c
        FROM meta_search_outcomes
        GROUP BY search_mode
        ORDER BY c DESC
    """).fetchall()

    return {
        'current_weights': weights,
        'effectiveness_7d': eff_7d,
        'effectiveness_30d': eff_30d,
        'effectiveness_all': eff_all,
        'weight_changes': weight_changes,
        'mode_distribution': [dict(r) for r in mode_dist],
        'meta_config_path': str(META_CONFIG_PATH)
    }
