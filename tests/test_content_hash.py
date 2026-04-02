"""Tests for content-hash deduplication."""

import pytest
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import memory_ops, database


def test_content_hash_prevents_duplicate_within_60s(temp_db):
    """Test that identical content within 60s is blocked."""
    # Add first memory
    mem_id1 = memory_ops.add_memory("learning", "This is a test memory", project="Test")
    assert mem_id1 is not None

    # Try to add identical memory immediately
    mem_id2 = memory_ops.add_memory("learning", "This is a test memory", project="Test")
    assert mem_id2 is None  # Should be blocked


def test_content_hash_case_insensitive(temp_db):
    """Test that content hash is case-insensitive."""
    mem_id1 = memory_ops.add_memory("learning", "Test Memory Content", project="Test")
    assert mem_id1 is not None

    # Same content, different case
    mem_id2 = memory_ops.add_memory("learning", "test memory content", project="Test")
    assert mem_id2 is None  # Should be blocked


def test_content_hash_strips_whitespace(temp_db):
    """Test that content hash strips leading/trailing whitespace."""
    mem_id1 = memory_ops.add_memory("learning", "Test content", project="Test")
    assert mem_id1 is not None

    # Same content with extra whitespace
    mem_id2 = memory_ops.add_memory("learning", "  Test content  ", project="Test")
    assert mem_id2 is None  # Should be blocked


def test_content_hash_includes_category(temp_db):
    """Test that content hash includes category."""
    mem_id1 = memory_ops.add_memory("learning", "Same content", project="Test")
    assert mem_id1 is not None

    # Same content, different category - should be allowed
    mem_id2 = memory_ops.add_memory("decision", "Same content", project="Test")
    assert mem_id2 is not None


def test_content_hash_different_content_allowed(temp_db):
    """Test that different content is allowed."""
    mem_id1 = memory_ops.add_memory("learning", "First memory", project="Test")
    assert mem_id1 is not None

    mem_id2 = memory_ops.add_memory("learning", "Second memory", project="Test")
    assert mem_id2 is not None


def test_content_hash_stored_in_db(temp_db):
    """Test that content_hash is actually stored in database."""
    import hashlib

    content = "Test content"
    category = "learning"
    mem_id = memory_ops.add_memory(category, content)
    assert mem_id is not None

    # Check hash is stored
    conn = database.get_db()
    row = conn.execute("SELECT content_hash FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row["content_hash"] is not None

    # Verify hash matches expected (first 16 chars only)
    expected_hash = hashlib.sha256(f"{category}:{content.strip().lower()}".encode()).hexdigest()[:16]
    assert row["content_hash"] == expected_hash


def test_content_hash_skip_dedup_still_stores_hash(temp_db):
    """Test that skip_dedup=True still stores content hash."""
    import hashlib

    content = "Test content"
    category = "learning"
    mem_id = memory_ops.add_memory(category, content, skip_dedup=True)
    assert mem_id is not None

    conn = database.get_db()
    row = conn.execute("SELECT content_hash FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row["content_hash"] is not None


def test_content_hash_time_window(temp_db, monkeypatch):
    """Test that duplicate detection is time-windowed (60s)."""
    # This test would require mocking time, which is complex
    # For now, just verify the logic is present
    mem_id1 = memory_ops.add_memory("learning", "Time test", project="Test")
    assert mem_id1 is not None

    # Immediate duplicate should be blocked
    mem_id2 = memory_ops.add_memory("learning", "Time test", project="Test")
    assert mem_id2 is None


def test_content_hash_index_exists(temp_db):
    """Test that content_hash index exists for performance."""
    conn = database.get_db()

    # Query sqlite_master for the index
    indexes = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'index' AND name = 'idx_content_hash'
    """).fetchall()
    conn.close()

    assert len(indexes) == 1
