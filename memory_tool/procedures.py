"""Procedural Memory with Failure Evolution (Upgrade 4)."""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from .config import get_logger
from .database import get_db

logger = get_logger(__name__)


def init_procedures_table() -> None:
    """Initialize the procedures table if it doesn't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            steps TEXT NOT NULL,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            last_refined_at TIMESTAMP,
            refinements TEXT DEFAULT '[]',
            project TEXT,
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_procedure(
    name: str,
    steps: List[str],
    project: Optional[str] = None,
    tags: Optional[str] = None
) -> bool:
    """
    Create a new procedure.

    Args:
        name: Unique procedure name
        steps: List of step descriptions
        project: Optional project association
        tags: Optional comma-separated tags

    Returns:
        True if created successfully, False if name already exists
    """
    init_procedures_table()
    conn = get_db()

    steps_json = json.dumps(steps)
    tags_json = json.dumps(tags.split(",") if tags else [])

    try:
        conn.execute("""
            INSERT INTO procedures (name, steps, project, tags)
            VALUES (?, ?, ?, ?)
        """, (name, steps_json, project, tags_json))
        conn.commit()
        conn.close()
        logger.info(f"Created procedure: {name} with {len(steps)} steps")
        return True
    except sqlite3.IntegrityError:
        conn.close()
        logger.error(f"Procedure '{name}' already exists")
        return False


def get_procedure(name: str) -> Optional[Dict[str, Any]]:
    """Get procedure by name."""
    init_procedures_table()
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM procedures WHERE name = ?",
        (name,)
    ).fetchone()

    conn.close()

    if not row:
        return None

    return {
        'id': row['id'],
        'name': row['name'],
        'steps': json.loads(row['steps']),
        'success_count': row['success_count'],
        'failure_count': row['failure_count'],
        'last_refined_at': row['last_refined_at'],
        'refinements': json.loads(row['refinements']),
        'project': row['project'],
        'tags': json.loads(row['tags']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'success_rate': _calc_success_rate(row['success_count'], row['failure_count'])
    }


def list_procedures(project: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all procedures, optionally filtered by project."""
    init_procedures_table()
    conn = get_db()

    if project:
        rows = conn.execute(
            "SELECT * FROM procedures WHERE project = ? ORDER BY name",
            (project,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM procedures ORDER BY name"
        ).fetchall()

    conn.close()

    procedures = []
    for row in rows:
        procedures.append({
            'id': row['id'],
            'name': row['name'],
            'steps': json.loads(row['steps']),
            'success_count': row['success_count'],
            'failure_count': row['failure_count'],
            'success_rate': _calc_success_rate(row['success_count'], row['failure_count']),
            'project': row['project'],
            'tags': json.loads(row['tags']),
            'created_at': row['created_at']
        })

    return procedures


def run_procedure(name: str) -> Optional[List[str]]:
    """
    Display procedure steps for execution.

    Args:
        name: Procedure name

    Returns:
        List of step descriptions, or None if not found
    """
    proc = get_procedure(name)
    if not proc:
        logger.error(f"Procedure '{name}' not found")
        return None

    return proc['steps']


def procedure_succeed(name: str) -> bool:
    """
    Mark procedure as successfully executed.

    Args:
        name: Procedure name

    Returns:
        True if updated, False if not found
    """
    init_procedures_table()
    conn = get_db()

    result = conn.execute("""
        UPDATE procedures
        SET success_count = success_count + 1,
            updated_at = datetime('now')
        WHERE name = ?
    """, (name,))

    updated = result.rowcount > 0
    conn.commit()
    conn.close()

    if updated:
        logger.info(f"Incremented success count for procedure: {name}")
    else:
        logger.error(f"Procedure '{name}' not found")

    return updated


def procedure_fail(name: str, what_went_wrong: str) -> bool:
    """
    Mark procedure as failed and add refinement note.

    Args:
        name: Procedure name
        what_went_wrong: Description of what failed

    Returns:
        True if updated, False if not found
    """
    init_procedures_table()
    conn = get_db()

    # Get current refinements
    row = conn.execute(
        "SELECT refinements FROM procedures WHERE name = ?",
        (name,)
    ).fetchone()

    if not row:
        conn.close()
        logger.error(f"Procedure '{name}' not found")
        return False

    refinements = json.loads(row['refinements'])

    # Add new refinement with timestamp
    refinements.append({
        'timestamp': datetime.now().isoformat(),
        'note': what_went_wrong
    })

    # Update procedure
    conn.execute("""
        UPDATE procedures
        SET failure_count = failure_count + 1,
            refinements = ?,
            last_refined_at = datetime('now'),
            updated_at = datetime('now')
        WHERE name = ?
    """, (json.dumps(refinements), name))

    conn.commit()
    conn.close()

    logger.info(f"Recorded failure for procedure: {name}")
    return True


def update_procedure_steps(name: str, new_steps: List[str]) -> bool:
    """
    Update procedure steps (for refinement after failures).

    Args:
        name: Procedure name
        new_steps: Updated list of steps

    Returns:
        True if updated, False if not found
    """
    init_procedures_table()
    conn = get_db()

    steps_json = json.dumps(new_steps)

    result = conn.execute("""
        UPDATE procedures
        SET steps = ?,
            updated_at = datetime('now')
        WHERE name = ?
    """, (steps_json, name))

    updated = result.rowcount > 0
    conn.commit()
    conn.close()

    if updated:
        logger.info(f"Updated steps for procedure: {name}")
    else:
        logger.error(f"Procedure '{name}' not found")

    return updated


def delete_procedure(name: str) -> bool:
    """Delete a procedure."""
    init_procedures_table()
    conn = get_db()

    result = conn.execute(
        "DELETE FROM procedures WHERE name = ?",
        (name,)
    )

    deleted = result.rowcount > 0
    conn.commit()
    conn.close()

    if deleted:
        logger.info(f"Deleted procedure: {name}")
    else:
        logger.error(f"Procedure '{name}' not found")

    return deleted


def _calc_success_rate(success: int, failure: int) -> float:
    """Calculate success rate as percentage."""
    total = success + failure
    if total == 0:
        return 0.0
    return round((success / total) * 100, 1)


def procedure_stats() -> Dict[str, Any]:
    """Get statistics about all procedures."""
    init_procedures_table()
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM procedures").fetchone()[0]

    total_successes = conn.execute(
        "SELECT SUM(success_count) FROM procedures"
    ).fetchone()[0] or 0

    total_failures = conn.execute(
        "SELECT SUM(failure_count) FROM procedures"
    ).fetchone()[0] or 0

    # Best performing procedure
    best = conn.execute("""
        SELECT name, success_count, failure_count
        FROM procedures
        WHERE (success_count + failure_count) > 0
        ORDER BY CAST(success_count AS FLOAT) / (success_count + failure_count) DESC
        LIMIT 1
    """).fetchone()

    # Most used procedure
    most_used = conn.execute("""
        SELECT name, (success_count + failure_count) as total
        FROM procedures
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    stats = {
        'total_procedures': total,
        'total_successes': total_successes,
        'total_failures': total_failures,
        'overall_success_rate': _calc_success_rate(total_successes, total_failures)
    }

    if best:
        stats['best_performer'] = {
            'name': best['name'],
            'success_rate': _calc_success_rate(best['success_count'], best['failure_count'])
        }

    if most_used:
        stats['most_used'] = {
            'name': most_used['name'],
            'executions': most_used['total']
        }

    return stats
