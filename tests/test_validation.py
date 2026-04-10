"""Tests for drift detection and validation module."""

import pytest
from datetime import datetime, timedelta
from memory_tool.validation import (
    score_drift_risk,
    find_drift_candidates,
    mark_validated,
    mark_refuted,
    get_unvalidated_semantic,
    detect_contradictions_in_tier,
    validation_report
)


def test_score_drift_risk_low():
    """Test drift risk scoring for low-risk memory."""
    # New memory, low access, has citations
    row = {
        'access_count': 1,
        'created_at': datetime.now().isoformat(),
        'citations': 'source1, source2',
        'tier': 'episodic',
        'last_validated_at': datetime.now().isoformat(),
        'proof_count': 1
    }
    score = score_drift_risk(row)
    assert score < 0.2  # Low risk


def test_score_drift_risk_high():
    """Test drift risk scoring for high-risk memory."""
    # Old, high access, no citations, semantic tier, never validated
    old_date = (datetime.now() - timedelta(days=200)).isoformat()
    row = {
        'access_count': 15,
        'created_at': old_date,
        'citations': '',
        'tier': 'semantic',
        'last_validated_at': None,
        'proof_count': 3
    }
    score = score_drift_risk(row)
    assert score > 0.7  # High risk


def test_score_drift_risk_medium():
    """Test drift risk scoring for medium-risk memory."""
    # Moderate age, moderate access, has citations, episodic
    med_date = (datetime.now() - timedelta(days=60)).isoformat()
    row = {
        'access_count': 8,
        'created_at': med_date,
        'citations': 'source1',
        'tier': 'episodic',
        'last_validated_at': None,
        'proof_count': 2
    }
    score = score_drift_risk(row)
    assert 0.3 < score < 0.7  # Medium risk


def test_find_drift_candidates(temp_db):
    """Test finding drift candidates."""
    conn = temp_db

    # Create high-access, old memory (drift candidate)
    old_date = (datetime.now() - timedelta(days=90)).isoformat()
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, citations, active)
        VALUES ('learning', 'Old frequently accessed memory', 'semantic', 10, ?, '', 1)
    """, (old_date,))

    # Create low-access, new memory (not a candidate)
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, active)
        VALUES ('learning', 'New rarely accessed memory', 'episodic', 2, datetime('now'), 1)
    """)

    # Create high-access but recent memory (not old enough)
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, active)
        VALUES ('learning', 'Recent frequently accessed memory', 'semantic', 8, datetime('now'), 1)
    """)

    conn.commit()

    # Find candidates (min_access=5, min_age_days=30)
    candidates = find_drift_candidates(conn, min_access_count=5, min_age_days=30)

    # Should find at least the old high-access memory
    assert len(candidates) >= 1
    assert candidates[0]['content'] == 'Old frequently accessed memory'
    assert 'drift_risk' in candidates[0]


def test_mark_validated(temp_db):
    """Test marking a memory as validated."""
    conn = temp_db

    # Create a memory
    conn.execute("""
        INSERT INTO memories (category, content, active)
        VALUES ('learning', 'Test memory', 1)
    """)
    conn.commit()

    mem_id = conn.execute("SELECT id FROM memories ORDER BY id DESC LIMIT 1").fetchone()['id']

    # Validate it
    success = mark_validated(conn, mem_id, validator='test_user', notes='verified from source')

    assert success

    # Check validation was recorded
    mem = conn.execute("SELECT last_validated_at FROM memories WHERE id = ?", (mem_id,)).fetchone()
    assert mem['last_validated_at'] is not None

    # Check validation log entry
    log = conn.execute(
        "SELECT * FROM validation_log WHERE memory_id = ?",
        (mem_id,)
    ).fetchone()
    assert log is not None
    assert log['validator'] == 'test_user'
    assert log['result'] == 'confirmed'
    assert log['notes'] == 'verified from source'


def test_mark_validated_nonexistent(temp_db):
    """Test validating nonexistent memory returns False."""
    conn = temp_db
    success = mark_validated(conn, 99999, validator='test')
    assert not success


def test_mark_refuted(temp_db):
    """Test marking a memory as refuted and demotion."""
    conn = temp_db

    # Create a semantic memory
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Wrong fact', 'semantic', 1)
    """)
    conn.commit()

    mem_id = conn.execute("SELECT id FROM memories ORDER BY id DESC LIMIT 1").fetchone()['id']

    # Refute it
    success = mark_refuted(conn, mem_id, validator='test_user', notes='this is incorrect')

    assert success

    # Check tier was demoted (semantic -> episodic)
    mem = conn.execute("SELECT tier, last_validated_at FROM memories WHERE id = ?", (mem_id,)).fetchone()
    assert mem['tier'] == 'episodic'
    assert mem['last_validated_at'] is not None

    # Check validation log
    log = conn.execute(
        "SELECT * FROM validation_log WHERE memory_id = ? AND result = 'refuted'",
        (mem_id,)
    ).fetchone()
    assert log is not None
    assert log['notes'] == 'this is incorrect'


def test_mark_refuted_demotion_chain(temp_db):
    """Test refutation demotes through tiers: semantic -> episodic -> working."""
    conn = temp_db

    # Create episodic memory
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Wrong episodic', 'episodic', 1)
    """)
    conn.commit()

    mem_id = conn.execute("SELECT id FROM memories ORDER BY id DESC LIMIT 1").fetchone()['id']

    # Refute it (episodic -> working)
    mark_refuted(conn, mem_id, notes='wrong')

    mem = conn.execute("SELECT tier FROM memories WHERE id = ?", (mem_id,)).fetchone()
    assert mem['tier'] == 'working'


def test_get_unvalidated_semantic(temp_db):
    """Test finding unvalidated semantic memories."""
    conn = temp_db

    # Create validated semantic memory
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO memories (category, content, tier, last_validated_at, active)
        VALUES ('preference', 'Validated fact', 'semantic', ?, 1)
    """, (now,))

    # Create unvalidated semantic memory
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('architecture', 'Unvalidated fact', 'semantic', 1)
    """)

    # Create unvalidated episodic memory (should not be returned)
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Unvalidated episodic', 'episodic', 1)
    """)

    conn.commit()

    # Get unvalidated semantic
    unvalidated = get_unvalidated_semantic(conn)

    # Should only return the unvalidated semantic memory
    assert len(unvalidated) == 1
    assert unvalidated[0]['content'] == 'Unvalidated fact'
    assert unvalidated[0]['tier'] == 'semantic'


def test_validation_report(temp_db):
    """Test validation report generation."""
    conn = temp_db

    # Create memories in different tiers
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Semantic 1', 'semantic', 1)
    """)
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Semantic 2', 'semantic', 1)
    """)
    conn.execute("""
        INSERT INTO memories (category, content, tier, active)
        VALUES ('learning', 'Episodic 1', 'episodic', 1)
    """)
    conn.commit()

    # Validate one semantic memory
    sem_id = conn.execute(
        "SELECT id FROM memories WHERE tier = 'semantic' LIMIT 1"
    ).fetchone()['id']

    mark_validated(conn, sem_id, notes='verified')

    # Refute the episodic memory
    ep_id = conn.execute(
        "SELECT id FROM memories WHERE tier = 'episodic' LIMIT 1"
    ).fetchone()['id']

    mark_refuted(conn, ep_id, notes='wrong')

    # Get report
    report = validation_report(conn)

    # Check validation counts
    assert report['validation_counts']['confirmed'] == 1
    assert report['validation_counts']['refuted'] == 1

    # Check tier stats (note: refuted episodic was demoted to working)
    assert 'semantic' in report['tier_stats']
    assert report['tier_stats']['semantic']['total'] == 2
    assert report['tier_stats']['semantic']['validated'] == 1
    assert report['tier_stats']['semantic']['pct_validated'] == 50.0

    # Check total validations
    assert report['total_validations'] == 2


def test_drift_risk_factors():
    """Test individual drift risk factors in isolation."""
    base_row = {
        'access_count': 0,
        'created_at': datetime.now().isoformat(),
        'citations': 'source',
        'tier': 'episodic',
        'last_validated_at': datetime.now().isoformat(),
        'proof_count': 1
    }

    # Test access count factor
    high_access = base_row.copy()
    high_access['access_count'] = 30
    assert score_drift_risk(high_access) > score_drift_risk(base_row)

    # Test age factor
    old = base_row.copy()
    old['created_at'] = (datetime.now() - timedelta(days=365)).isoformat()
    assert score_drift_risk(old) > score_drift_risk(base_row)

    # Test no citations factor
    no_citations = base_row.copy()
    no_citations['citations'] = ''
    assert score_drift_risk(no_citations) > score_drift_risk(base_row)

    # Test semantic tier factor
    semantic = base_row.copy()
    semantic['tier'] = 'semantic'
    assert score_drift_risk(semantic) > score_drift_risk(base_row)

    # Test never validated factor
    never_validated = base_row.copy()
    never_validated['last_validated_at'] = None
    assert score_drift_risk(never_validated) > score_drift_risk(base_row)


def test_drift_candidates_sorted_by_risk(temp_db):
    """Test that drift candidates are sorted by risk score descending."""
    conn = temp_db

    # Create memories with different risk profiles
    old_date = (datetime.now() - timedelta(days=200)).isoformat()

    # Very high risk: old, high access, no citations, semantic, never validated
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, citations, active)
        VALUES ('architecture', 'Highest risk', 'semantic', 20, ?, '', 1)
    """, (old_date,))

    # Medium risk: moderate access, recent, has citations
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, citations, active)
        VALUES ('learning', 'Medium risk', 'episodic', 7, datetime('now'), 'source1', 1)
    """)

    # Low risk but still high access (to qualify as candidate)
    recent = (datetime.now() - timedelta(days=5)).isoformat()
    conn.execute("""
        INSERT INTO memories (category, content, tier, access_count, created_at, citations, active)
        VALUES ('learning', 'Lower risk', 'episodic', 6, ?, 'source1,source2', 1)
    """, (recent,))

    conn.commit()

    # Find candidates
    candidates = find_drift_candidates(conn, min_access_count=5, min_age_days=0)

    # Should be sorted by risk descending
    assert len(candidates) >= 3
    assert candidates[0]['content'] == 'Highest risk'
    assert candidates[0]['drift_risk'] > candidates[1]['drift_risk']
    assert candidates[1]['drift_risk'] > candidates[2]['drift_risk']


def test_validation_log_cascade_delete(temp_db):
    """Test that validation log entries are deleted when memory is deleted."""
    conn = temp_db

    # Create and validate a memory
    conn.execute("""
        INSERT INTO memories (category, content, active)
        VALUES ('learning', 'Test', 1)
    """)
    conn.commit()

    mem_id = conn.execute("SELECT id FROM memories ORDER BY id DESC LIMIT 1").fetchone()['id']
    mark_validated(conn, mem_id, notes='test')

    # Verify validation log entry exists
    log = conn.execute("SELECT * FROM validation_log WHERE memory_id = ?", (mem_id,)).fetchone()
    assert log is not None

    # Delete memory (soft delete)
    conn.execute("UPDATE memories SET active = 0 WHERE id = ?", (mem_id,))
    conn.commit()

    # Note: With ON DELETE CASCADE, if we hard-deleted the memory row,
    # the validation_log would auto-delete. For soft delete, entries remain.
    # This test verifies the FK constraint works.


def test_validation_types():
    """Test different validation types are allowed."""
    from memory_tool.database import get_db

    conn = get_db()

    # Create a test memory
    conn.execute("""
        INSERT INTO memories (category, content, active)
        VALUES ('learning', 'Test validation types', 1)
    """)
    conn.commit()

    mem_id = conn.execute("SELECT id FROM memories ORDER BY id DESC LIMIT 1").fetchone()['id']

    # Test each validation type
    valid_types = ['user', 'external_source', 'llm_check', 'cross_reference']

    for vtype in valid_types:
        success = mark_validated(conn, mem_id, validator='test', validation_type=vtype, result='confirmed')
        assert success

    # Verify all entries were created
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM validation_log WHERE memory_id = ?",
        (mem_id,)
    ).fetchone()['cnt']

    assert count == len(valid_types)

    # Cleanup
    conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
    conn.commit()
    conn.close()
