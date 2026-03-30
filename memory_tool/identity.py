"""Identity Layer — discovers behavioral traits from memory patterns.

Mines past decisions, errors, beliefs, and learnings to build a profile
of behavioral tendencies, preferences, and patterns.
"""

import sqlite3
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from .database import get_db
from .config import get_logger

logger = get_logger(__name__)


# Trait detection patterns — maps keywords/patterns to trait names
TRAIT_PATTERNS = {
    'prefers_docker': {
        'keywords': ['docker', 'container', 'docker-compose', 'dockerfile'],
        'anti_keywords': ['pm2', 'systemd', 'bare metal'],
        'description': 'Prefers Docker for service deployment'
    },
    'prefers_pm2': {
        'keywords': ['pm2', 'pm2 restart', 'pm2 logs'],
        'anti_keywords': ['docker', 'container'],
        'description': 'Prefers PM2 for process management'
    },
    'over_engineers': {
        'keywords': ['refactor', 'abstraction', 'service layer', 'over-engineer', 'too complex'],
        'anti_keywords': ['simple', 'quick fix', 'bash script'],
        'description': 'Tendency to over-engineer solutions'
    },
    'ships_fast': {
        'keywords': ['ship it', 'mvp', 'quick', 'hack', 'prototype', 'just works'],
        'anti_keywords': ['refactor', 'proper', 'clean'],
        'description': 'Prioritizes shipping over perfection'
    },
    'tests_first': {
        'keywords': ['test first', 'tdd', 'test-driven', 'write tests'],
        'anti_keywords': ['skip tests', 'no tests'],
        'description': 'Writes tests before implementation'
    },
    'prefers_typescript': {
        'keywords': ['typescript', '.ts', 'type-safe', 'interfaces'],
        'anti_keywords': ['javascript', 'no types'],
        'description': 'Prefers TypeScript over JavaScript'
    },
    'prefers_python': {
        'keywords': ['python', '.py', 'pip', 'pytest'],
        'anti_keywords': [],
        'description': 'Uses Python for tooling and scripts'
    },
    'cautious_deployer': {
        'keywords': ['backup before', 'rollback', 'blue-green', 'canary', 'careful'],
        'anti_keywords': ['yolo', 'force push', 'just deploy'],
        'description': 'Takes cautious approach to deployments'
    },
    'automation_first': {
        'keywords': ['automate', 'cron', 'hook', 'ci/cd', 'pipeline', 'script'],
        'anti_keywords': ['manual', 'by hand'],
        'description': 'Automates repetitive tasks'
    },
    'docs_writer': {
        'keywords': ['document', 'readme', 'docs', 'changelog', 'wiki'],
        'anti_keywords': [],
        'description': 'Values documentation'
    },
    'sqlite_lover': {
        'keywords': ['sqlite', 'sqlite3', 'fts5', 'sqlite-vec'],
        'anti_keywords': ['postgres only', 'mysql'],
        'description': 'Prefers SQLite for local data'
    },
    'monorepo_style': {
        'keywords': ['monorepo', 'shared', 'workspace'],
        'anti_keywords': ['microservice', 'separate repo'],
        'description': 'Prefers monorepo project structure'
    },
}


def init_identity_tables(db: sqlite3.Connection) -> None:
    """Create identity tracking tables."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS identity_traits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trait_name TEXT UNIQUE NOT NULL,
            description TEXT,
            confidence REAL DEFAULT 0.5,
            evidence_count INTEGER DEFAULT 0,
            counter_evidence INTEGER DEFAULT 0,
            memory_ids TEXT DEFAULT '[]',
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS identity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            traits TEXT NOT NULL,
            trait_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_identity_trait_name ON identity_traits(trait_name);
        CREATE INDEX IF NOT EXISTS idx_identity_confidence ON identity_traits(confidence);
    """)
    db.commit()


def discover_traits(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Mine memories to discover behavioral traits.

    Scans all active memories for trait patterns and calculates
    confidence based on evidence frequency.

    Args:
        db: Database connection

    Returns:
        List of discovered traits with confidence scores
    """
    init_identity_tables(db)

    # Get all active memories
    memories = db.execute("""
        SELECT id, content, category, project, tags, created_at
        FROM memories
        WHERE active = 1
        ORDER BY created_at DESC
    """).fetchall()

    if not memories:
        return []

    # Score each trait pattern against memories
    trait_scores = {}

    for trait_name, pattern in TRAIT_PATTERNS.items():
        evidence_ids = []
        counter_ids = []

        for mem in memories:
            content = (mem['content'] + ' ' + (mem['tags'] or '')).lower()

            # Check for positive keywords
            has_keyword = any(kw.lower() in content for kw in pattern['keywords'])
            has_anti = any(kw.lower() in content for kw in pattern['anti_keywords']) if pattern['anti_keywords'] else False

            if has_keyword and not has_anti:
                evidence_ids.append(mem['id'])
            elif has_anti and not has_keyword:
                counter_ids.append(mem['id'])

        if evidence_ids:
            # Calculate confidence: evidence / (evidence + counter_evidence)
            evidence = len(evidence_ids)
            counter = len(counter_ids)
            confidence = evidence / (evidence + counter) if (evidence + counter) > 0 else 0.5

            # Boost confidence if seen across multiple projects
            projects = set()
            for mem in memories:
                if mem['id'] in evidence_ids and mem['project']:
                    projects.add(mem['project'])
            if len(projects) > 1:
                confidence = min(0.99, confidence + 0.1)

            trait_scores[trait_name] = {
                'trait_name': trait_name,
                'description': pattern['description'],
                'confidence': round(confidence, 2),
                'evidence_count': evidence,
                'counter_evidence': counter,
                'memory_ids': evidence_ids[:20],  # Keep top 20
                'projects': list(projects)
            }

    # Also discover custom traits from decision/learning categories
    custom_traits = _discover_custom_traits(db, memories)
    trait_scores.update(custom_traits)

    # Save to database
    for name, trait in trait_scores.items():
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count, counter_evidence, memory_ids, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(trait_name) DO UPDATE SET
                confidence = excluded.confidence,
                evidence_count = excluded.evidence_count,
                counter_evidence = excluded.counter_evidence,
                memory_ids = excluded.memory_ids,
                last_seen = datetime('now')
        """, (
            name, trait['description'], trait['confidence'],
            trait['evidence_count'], trait['counter_evidence'],
            str(trait['memory_ids'])
        ))

    db.commit()

    # Return sorted by confidence
    results = sorted(trait_scores.values(), key=lambda x: -x['confidence'])
    return results


def _discover_custom_traits(db: sqlite3.Connection, memories: list) -> Dict[str, Dict[str, Any]]:
    """Discover custom traits from decision and error patterns.

    Looks for recurring themes in decisions, errors, and learnings
    that aren't covered by predefined TRAIT_PATTERNS.

    Args:
        db: Database connection
        memories: List of memory rows

    Returns:
        Dict of trait_name → trait info
    """
    custom = {}

    # Analyze decisions for patterns
    decisions = [m for m in memories if m['category'] in ('decision', 'preference')]
    if decisions:
        # Find common words across decisions (excluding stop words)
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'shall', 'to',
            'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'and', 'or', 'but', 'not', 'if', 'then', 'so', 'as',
            'it', 'this', 'that', 'these', 'those', 'i', 'we', 'you',
            'use', 'using', 'used', 'new', 'add', 'added', 'all'
        }

        word_counter = Counter()
        for d in decisions:
            words = re.findall(r'\b[a-z]{3,}\b', d['content'].lower())
            meaningful = [w for w in words if w not in stop_words]
            word_counter.update(meaningful)

        # Top recurring themes in decisions
        for word, count in word_counter.most_common(5):
            if count >= 3:  # At least 3 occurrences
                trait_name = f"decides_{word}"
                relevant_ids = [
                    m['id'] for m in decisions
                    if word in m['content'].lower()
                ]
                custom[trait_name] = {
                    'trait_name': trait_name,
                    'description': f"Frequently decides about '{word}' ({count} times)",
                    'confidence': min(0.9, 0.3 + count * 0.1),
                    'evidence_count': count,
                    'counter_evidence': 0,
                    'memory_ids': relevant_ids[:20],
                    'projects': []
                }

    # Analyze errors for recurring patterns
    errors = [m for m in memories if m['category'] == 'error']
    if len(errors) >= 3:
        error_words = Counter()
        error_stop = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'shall', 'to',
            'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'and', 'or', 'but', 'not', 'if', 'then', 'so', 'as',
            'it', 'this', 'that', 'these', 'those', 'i', 'we', 'you',
            'use', 'using', 'used', 'new', 'add', 'added', 'all',
            'error', 'failed', 'command', 'exit', 'code'
        }
        for e in errors:
            words = re.findall(r'\b[a-z]{3,}\b', e['content'].lower())
            stop_words_plus = error_stop
            meaningful = [w for w in words if w not in stop_words_plus]
            error_words.update(meaningful)

        for word, count in error_words.most_common(3):
            if count >= 3:
                trait_name = f"error_prone_{word}"
                relevant_ids = [m['id'] for m in errors if word in m['content'].lower()]
                custom[trait_name] = {
                    'trait_name': trait_name,
                    'description': f"Recurring errors related to '{word}' ({count} times)",
                    'confidence': min(0.9, 0.3 + count * 0.1),
                    'evidence_count': count,
                    'counter_evidence': 0,
                    'memory_ids': relevant_ids[:20],
                    'projects': []
                }

    return custom


def get_identity(db: sqlite3.Connection, min_confidence: float = 0.3) -> Dict[str, Any]:
    """Get the current identity profile.

    Args:
        db: Database connection
        min_confidence: Minimum confidence threshold for traits

    Returns:
        Dict with identity profile: traits, stats, and summary
    """
    init_identity_tables(db)

    traits = db.execute("""
        SELECT * FROM identity_traits
        WHERE active = 1 AND confidence >= ?
        ORDER BY confidence DESC
    """, (min_confidence,)).fetchall()

    trait_list = [dict(t) for t in traits]

    # Generate summary
    strong_traits = [t for t in trait_list if t['confidence'] >= 0.7]
    moderate_traits = [t for t in trait_list if 0.4 <= t['confidence'] < 0.7]
    weak_traits = [t for t in trait_list if t['confidence'] < 0.4]

    # Total evidence
    total_evidence = sum(t['evidence_count'] for t in trait_list)

    return {
        'traits': trait_list,
        'strong': strong_traits,
        'moderate': moderate_traits,
        'weak': weak_traits,
        'total_traits': len(trait_list),
        'total_evidence': total_evidence,
        'summary': _generate_identity_summary(strong_traits, moderate_traits)
    }


def _generate_identity_summary(strong: List[Dict], moderate: List[Dict]) -> str:
    """Generate a human-readable identity summary."""
    lines = []

    if strong:
        lines.append("Core traits:")
        for t in strong[:5]:
            lines.append(f"  • {t['description']} ({t['confidence']:.0%} confident, {t['evidence_count']} evidence)")

    if moderate:
        lines.append("Emerging traits:")
        for t in moderate[:5]:
            lines.append(f"  ○ {t['description']} ({t['confidence']:.0%} confident)")

    if not lines:
        return "No significant traits discovered yet. Add more memories to build your identity profile."

    return "\n".join(lines)


def save_identity_snapshot(db: sqlite3.Connection) -> int:
    """Save current identity state as a snapshot for tracking evolution.

    Args:
        db: Database connection

    Returns:
        Snapshot ID
    """
    init_identity_tables(db)

    traits = db.execute("""
        SELECT trait_name, confidence, evidence_count
        FROM identity_traits WHERE active = 1
        ORDER BY confidence DESC
    """).fetchall()

    import json
    trait_data = [dict(t) for t in traits]

    cursor = db.execute("""
        INSERT INTO identity_snapshots (traits, trait_count)
        VALUES (?, ?)
    """, (json.dumps(trait_data), len(trait_data)))

    db.commit()
    return cursor.lastrowid


def get_identity_evolution(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get identity evolution over time from snapshots.

    Args:
        db: Database connection
        limit: Max snapshots to return

    Returns:
        List of snapshot dicts with parsed traits
    """
    init_identity_tables(db)

    rows = db.execute("""
        SELECT * FROM identity_snapshots
        ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()

    import json
    results = []
    for row in rows:
        entry = dict(row)
        try:
            entry['traits'] = json.loads(entry['traits'])
        except (json.JSONDecodeError, TypeError):
            entry['traits'] = []
        results.append(entry)

    return results


def compare_identity_snapshots(db: sqlite3.Connection) -> Dict[str, Any]:
    """Compare latest identity snapshot with previous to show evolution.

    Args:
        db: Database connection

    Returns:
        Dict with new traits, removed traits, and confidence changes
    """
    snapshots = get_identity_evolution(db, limit=2)

    if len(snapshots) < 2:
        return {
            'has_comparison': False,
            'message': 'Need at least 2 snapshots for comparison'
        }

    current = {t['trait_name']: t for t in snapshots[0]['traits']}
    previous = {t['trait_name']: t for t in snapshots[1]['traits']}

    new_traits = [t for name, t in current.items() if name not in previous]
    removed_traits = [t for name, t in previous.items() if name not in current]

    changed = []
    for name, curr_trait in current.items():
        if name in previous:
            prev_trait = previous[name]
            delta = curr_trait['confidence'] - prev_trait['confidence']
            if abs(delta) > 0.05:  # Significant change
                changed.append({
                    'trait_name': name,
                    'old_confidence': prev_trait['confidence'],
                    'new_confidence': curr_trait['confidence'],
                    'delta': delta
                })

    return {
        'has_comparison': True,
        'current_date': snapshots[0]['created_at'],
        'previous_date': snapshots[1]['created_at'],
        'new_traits': new_traits,
        'removed_traits': removed_traits,
        'changed': sorted(changed, key=lambda x: -abs(x['delta']))
    }
