"""Unit tests for Circus sync integration."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from memory_tool.circus_sync import CircusSync, init_circus_sync


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize basic schema
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    yield str(db_path)

    # Cleanup
    db_path.unlink(missing_ok=True)


class TestCircusSync:
    """Test Circus sync functionality."""

    def test_ensure_tables_creates_tables(self, temp_db):
        """Test that ensure_tables creates required tables."""
        sync = CircusSync(temp_db)
        sync.ensure_tables()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check circus_sync_state table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='circus_sync_state'
        """)
        assert cursor.fetchone() is not None

        # Check circus_memory_map table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='circus_memory_map'
        """)
        assert cursor.fetchone() is not None

        conn.close()

    def test_init_circus_sync(self, temp_db):
        """Test init_circus_sync helper function."""
        sync = init_circus_sync(temp_db)

        assert isinstance(sync, CircusSync)
        assert sync.db_path == temp_db

        # Verify tables were created
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('circus_sync_state', 'circus_memory_map')
        """)
        tables = cursor.fetchall()
        assert len(tables) == 2
        conn.close()

    def test_is_connected_false_without_token(self, temp_db):
        """Test is_connected returns False without token."""
        sync = CircusSync(temp_db)
        sync.agent_token = ""

        assert sync.is_connected() is False

    def test_is_connected_true_with_token(self, temp_db):
        """Test is_connected returns True with token."""
        sync = CircusSync(temp_db)
        sync.agent_token = "test-token"

        assert sync.is_connected() is True

    def test_auto_publish_disabled(self, temp_db):
        """Test auto_publish does nothing when disabled."""
        sync = CircusSync(temp_db)
        sync.auto_publish = False
        sync.agent_token = "test-token"

        # Should not raise, should do nothing
        sync.auto_publish_on_add(
            memory_id=1,
            content="test memory",
            category="learning",
            tags="test",
            confidence=0.9
        )

    def test_auto_publish_skips_pending_category(self, temp_db):
        """Test auto_publish skips pending category."""
        sync = CircusSync(temp_db)
        sync.auto_publish = True
        sync.agent_token = "test-token"

        # Should not raise, should skip
        sync.auto_publish_on_add(
            memory_id=1,
            content="test memory",
            category="pending",  # Should be skipped
            tags="test",
            confidence=0.9
        )

    def test_auto_publish_skips_error_category(self, temp_db):
        """Test auto_publish skips error category."""
        sync = CircusSync(temp_db)
        sync.auto_publish = True
        sync.agent_token = "test-token"

        # Should not raise, should skip
        sync.auto_publish_on_add(
            memory_id=1,
            content="test memory",
            category="error",  # Should be skipped
            tags="test",
            confidence=0.9
        )

    def test_auto_publish_privacy_tier_from_tags(self, temp_db):
        """Test privacy tier detection from tags."""
        sync = CircusSync(temp_db)
        sync.ensure_tables()

        # Test that tags affect privacy tier (we can't test actual publish without mock)
        # But we can test the tag parsing logic indirectly

        # This would need mocking of requests.post to test fully
        # For now, just test it doesn't crash
        sync.auto_publish = False  # Don't actually try to publish
        sync.auto_publish_on_add(
            memory_id=1,
            content="test",
            category="learning",
            tags='["private", "test"]',
            confidence=0.9
        )
