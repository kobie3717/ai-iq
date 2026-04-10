"""Tests for memory tier management."""

import pytest
from datetime import datetime, timedelta
from memory_tool.tiers import (
    classify_tier,
    promote_tier_pass,
    demote_tier_pass,
    expire_working,
    tier_stats,
    promote_memory_to_tier,
    demote_memory_to_tier
)


def test_classify_tier_working():
    """Test classification of working tier memories."""
    # Pending category -> working
    row = {'category': 'pending', 'priority': 0, 'tags': '', 'proof_count': 1, 'expires_at': None, 'access_count': 0}
    assert classify_tier(row) == 'working'

    # Error category -> working
    row = {'category': 'error', 'priority': 0, 'tags': '', 'proof_count': 1, 'expires_at': None, 'access_count': 0}
    assert classify_tier(row) == 'working'

    # Expires within 24h -> working
    exp_dt = (datetime.now() + timedelta(hours=12)).isoformat()
    row = {'category': 'learning', 'priority': 0, 'tags': '', 'proof_count': 1, 'expires_at': exp_dt, 'access_count': 0}
    assert classify_tier(row) == 'working'


def test_classify_tier_semantic():
    """Test classification of semantic tier memories."""
    # Preference with high proof_count -> semantic
    row = {'category': 'preference', 'priority': 5, 'tags': '', 'proof_count': 3, 'expires_at': None, 'access_count': 0}
    assert classify_tier(row) == 'semantic'

    # Architecture with high proof_count -> semantic
    row = {'category': 'architecture', 'priority': 7, 'tags': '', 'proof_count': 3, 'expires_at': None, 'access_count': 0}
    assert classify_tier(row) == 'semantic'

    # High access + high proof -> semantic
    row = {'category': 'learning', 'priority': 0, 'tags': '', 'proof_count': 3, 'expires_at': None, 'access_count': 5}
    assert classify_tier(row) == 'semantic'


def test_classify_tier_episodic():
    """Test classification of episodic tier memories (default)."""
    # Regular learning -> episodic
    row = {'category': 'learning', 'priority': 0, 'tags': '', 'proof_count': 1, 'expires_at': None, 'access_count': 0}
    assert classify_tier(row) == 'episodic'

    # Decision -> episodic
    row = {'category': 'decision', 'priority': 5, 'tags': '', 'proof_count': 1, 'expires_at': None, 'access_count': 2}
    assert classify_tier(row) == 'episodic'


def test_promote_tier_pass(temp_db):
    """Test automatic promotion from episodic to semantic."""
    conn = temp_db

    # Create episodic memories with varying proof/access counts
    conn.execute("""
        INSERT INTO memories (category, content, tier, proof_count, access_count, active)
        VALUES ('preference', 'User prefers dark mode', 'episodic', 3, 5, 1)
    """)
    conn.execute("""
        INSERT INTO memories (category, content, tier, proof_count, access_count, active)
        VALUES ('architecture', 'Use Redux for state', 'episodic', 4, 6, 1)
    """)
    # This one should NOT be promoted (low access)
    conn.execute("""
        INSERT INTO memories (category, content, tier, proof_count, access_count, active)
        VALUES ('learning', 'Some tip', 'episodic', 3, 2, 1)
    """)
    conn.commit()

    # Run promotion
    promoted = promote_tier_pass(conn)
    assert promoted == 2  # Only the first two should be promoted

    # Verify tiers
    rows = conn.execute("SELECT tier FROM memories WHERE active = 1 ORDER BY id").fetchall()
    assert rows[0]['tier'] == 'semantic'
    assert rows[1]['tier'] == 'semantic'
    assert rows[2]['tier'] == 'episodic'


def test_demote_tier_pass(temp_db):
    """Test automatic demotion from semantic to episodic."""
    conn = temp_db

    # Create semantic memories
    conn.execute("""
        INSERT INTO memories (category, content, tier, stale, access_count, active)
        VALUES ('learning', 'Stale learning', 'semantic', 1, 1, 1)
    """)
    # This one should NOT be demoted (preference stays semantic)
    conn.execute("""
        INSERT INTO memories (category, content, tier, stale, access_count, active)
        VALUES ('preference', 'User preference', 'semantic', 1, 1, 1)
    """)
    # This one should NOT be demoted (not stale)
    conn.execute("""
        INSERT INTO memories (category, content, tier, stale, access_count, active)
        VALUES ('learning', 'Active learning', 'semantic', 0, 1, 1)
    """)
    conn.commit()

    # Run demotion
    demoted = demote_tier_pass(conn)
    assert demoted == 1  # Only the first one should be demoted

    # Verify tiers
    rows = conn.execute("SELECT tier FROM memories WHERE active = 1 ORDER BY id").fetchall()
    assert rows[0]['tier'] == 'episodic'
    assert rows[1]['tier'] == 'semantic'  # Preference stays semantic
    assert rows[2]['tier'] == 'semantic'  # Not stale, stays semantic


def test_expire_working(temp_db):
    """Test expiration of old working tier memories."""
    conn = temp_db

    # Create working memories with different ages
    old_dt = (datetime.now() - timedelta(hours=25)).isoformat()
    recent_dt = (datetime.now() - timedelta(hours=1)).isoformat()

    conn.execute("""
        INSERT INTO memories (category, content, tier, created_at, access_count, active)
        VALUES ('pending', 'Old pending', 'working', ?, 0, 1)
    """, (old_dt,))
    conn.execute("""
        INSERT INTO memories (category, content, tier, created_at, access_count, active)
        VALUES ('pending', 'Recent pending', 'working', ?, 0, 1)
    """, (recent_dt,))
    # This one should NOT expire (has been accessed)
    conn.execute("""
        INSERT INTO memories (category, content, tier, created_at, access_count, active)
        VALUES ('error', 'Old error accessed', 'working', ?, 2, 1)
    """, (old_dt,))
    conn.commit()

    # Run expiration
    expired = expire_working(conn)
    assert expired == 1  # Only the old, never-accessed one

    # Verify active status
    rows = conn.execute("SELECT active FROM memories ORDER BY id").fetchall()
    assert rows[0]['active'] == 0  # Expired
    assert rows[1]['active'] == 1  # Still active (recent)
    assert rows[2]['active'] == 1  # Still active (accessed)


def test_tier_stats(temp_db):
    """Test tier statistics calculation."""
    conn = temp_db

    # Create memories in different tiers
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'A', 'working', 1)")
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'B', 'working', 1)")
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'C', 'episodic', 1)")
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'D', 'episodic', 1)")
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'E', 'episodic', 1)")
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'F', 'semantic', 1)")
    # Inactive memory (should not be counted)
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'G', 'semantic', 0)")
    conn.commit()

    # Get stats
    stats = tier_stats(conn)
    assert stats['working'] == 2
    assert stats['episodic'] == 3
    assert stats['semantic'] == 1
    assert stats['total'] == 6


def test_promote_memory_to_tier(temp_db):
    """Test manual promotion of memory to specific tier."""
    conn = temp_db

    # Create a memory
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'Test', 'episodic', 1)")
    conn.commit()
    mem_id = conn.execute("SELECT id FROM memories").fetchone()['id']

    # Promote to semantic
    promote_memory_to_tier(conn, mem_id, 'semantic')

    # Verify
    tier = conn.execute("SELECT tier FROM memories WHERE id = ?", (mem_id,)).fetchone()['tier']
    assert tier == 'semantic'


def test_demote_memory_to_tier(temp_db):
    """Test manual demotion of memory to specific tier."""
    conn = temp_db

    # Create a semantic memory
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'Test', 'semantic', 1)")
    conn.commit()
    mem_id = conn.execute("SELECT id FROM memories").fetchone()['id']

    # Demote to episodic
    demote_memory_to_tier(conn, mem_id, 'episodic')

    # Verify
    tier = conn.execute("SELECT tier FROM memories WHERE id = ?", (mem_id,)).fetchone()['tier']
    assert tier == 'episodic'


def test_invalid_tier_raises_error(temp_db):
    """Test that invalid tier names raise ValueError."""
    conn = temp_db

    # Create a memory
    conn.execute("INSERT INTO memories (category, content, tier, active) VALUES ('learning', 'Test', 'episodic', 1)")
    conn.commit()
    mem_id = conn.execute("SELECT id FROM memories").fetchone()['id']

    # Try to promote to invalid tier
    with pytest.raises(ValueError):
        promote_memory_to_tier(conn, mem_id, 'invalid')

    # Try to demote to invalid tier
    with pytest.raises(ValueError):
        demote_memory_to_tier(conn, mem_id, 'invalid')


def test_nonexistent_memory_raises_error(temp_db):
    """Test that operations on nonexistent memory raise ValueError."""
    conn = temp_db

    # Try to promote nonexistent memory
    with pytest.raises(ValueError):
        promote_memory_to_tier(conn, 99999, 'semantic')

    # Try to demote nonexistent memory
    with pytest.raises(ValueError):
        demote_memory_to_tier(conn, 99999, 'episodic')
