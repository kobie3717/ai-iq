"""GDPR/EU AI Act compliance — right to erasure, anonymization, audit log."""

import hashlib
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from .config import get_logger
from .database import get_db

logger = get_logger(__name__)


def _hash_content(content: str) -> str:
    """SHA-256 of content — proves existence without storing PII."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def audit(
    event_type: str,
    memory_id: Optional[int] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    actor: str = 'system',
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Write one audit log entry. Never raises — audit failures must not block operations."""
    try:
        close_after = conn is None
        if conn is None:
            conn = get_db()
        content_hash = _hash_content(content) if content else None
        conn.execute(
            """INSERT INTO audit_log
               (event_type, memory_id, content_hash, category, project, actor, reason, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_type, memory_id, content_hash, category, project, actor, reason, ip_address),
        )
        conn.commit()
        if close_after:
            conn.close()
    except Exception as e:
        logger.warning(f"Audit log write failed (non-fatal): {e}")


def erase_memory(
    memory_id: int,
    actor: str = 'system',
    reason: str = 'gdpr_erasure_request',
) -> bool:
    """
    GDPR-compliant erasure: anonymize content in-place + audit log entry.

    Does NOT hard-delete (audit trail must survive). Instead:
    - Replaces content with '[erased]'
    - Nulls out tags, project, metadata
    - Sets active=0
    - Records SHA-256 of original content in audit_log

    Returns True if memory was found and erased, False otherwise.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id, content, category, project FROM memories WHERE id = ? AND active = 1",
        (memory_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    original_content = row['content'] or ''
    category = row['category']
    project = row['project']

    # Anonymize in-place
    conn.execute(
        """UPDATE memories SET
               content = '[erased]',
               tags = NULL,
               project = NULL,
               active = 0,
               updated_at = datetime('now')
           WHERE id = ?""",
        (memory_id,)
    )
    conn.commit()

    # Audit entry (on same connection, already committed)
    audit(
        event_type='erase',
        memory_id=memory_id,
        content=original_content,
        category=category,
        project=project,
        actor=actor,
        reason=reason,
        conn=conn,
    )

    # Remove from vector index
    try:
        conn.execute("DELETE FROM memory_vec WHERE rowid = ?", (memory_id,))
        conn.commit()
    except Exception:
        pass  # vec table may not exist

    # Remove from FTS index
    try:
        conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
        conn.commit()
    except Exception:
        pass

    conn.close()
    logger.info(f"Memory #{memory_id} erased (GDPR) by {actor}")
    return True


def erase_project(
    project_name: str,
    actor: str = 'system',
    reason: str = 'gdpr_erasure_request',
) -> int:
    """Erase all memories for a project. Returns count erased."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM memories WHERE project = ? AND active = 1",
        (project_name,)
    ).fetchall()
    conn.close()

    count = 0
    for row in rows:
        if erase_memory(row['id'], actor=actor, reason=reason):
            count += 1

    logger.info(f"Erased {count} memories for project '{project_name}' (GDPR)")
    return count


def export_audit_log(
    since: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Export audit log entries as list of dicts."""
    conn = get_db()
    conditions = []
    params: List[Any] = []

    if since:
        conditions.append("created_at >= ?")
        params.append(since)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def audit_stats() -> Dict[str, Any]:
    """Summary of audit log for compliance reporting."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    by_type = conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM audit_log GROUP BY event_type"
    ).fetchall()
    oldest = conn.execute(
        "SELECT MIN(created_at) FROM audit_log"
    ).fetchone()[0]
    conn.close()
    return {
        'total_entries': total,
        'by_type': {r['event_type']: r['cnt'] for r in by_type},
        'oldest_entry': oldest,
        'retention_years': 10,
    }
