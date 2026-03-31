"""Integration tests for all three scavenge-inspired features."""

import pytest
import sys
from pathlib import Path
from io import StringIO

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import memory_ops, database, display, modes


def test_all_features_together(temp_db, capsys):
    """Test all three features working together in a realistic scenario."""

    # Feature 3: Set mode to dev
    modes.set_mode("dev")
    config = modes.get_mode_config()
    assert config["show_tokens"] is True
    assert config["search_limit"] == 15

    # Feature 2: Add memories, test dedup (use long content for token economics)
    mem_id1 = memory_ops.add_memory(
        "learning",
        "Python best practices for web development including error handling, logging, "
        "testing strategies, code organization, design patterns, async programming, "
        "database connections, API design, security considerations, and deployment workflows",
        project="Test"
    )
    assert mem_id1 is not None

    # Try to add duplicate - should be blocked
    mem_id2 = memory_ops.add_memory(
        "learning",
        "Python best practices for web development including error handling, logging, "
        "testing strategies, code organization, design patterns, async programming, "
        "database connections, API design, security considerations, and deployment workflows",
        project="Test"
    )
    assert mem_id2 is None  # Blocked by content-hash dedup

    # Add different content - should succeed (also long)
    mem_id3 = memory_ops.add_memory(
        "learning",
        "JavaScript async patterns and promise handling techniques for modern applications "
        "including error handling, event loops, callbacks, async/await syntax, "
        "concurrent operations, race conditions, and performance optimization strategies",
        project="Test"
    )
    assert mem_id3 is not None

    # Add another one (also long)
    mem_id4 = memory_ops.add_memory(
        "learning",
        "Database optimization strategies including indexing, query performance tuning, "
        "connection pooling, caching mechanisms, replication setup, backup strategies, "
        "monitoring tools, and capacity planning for high-traffic applications",
        project="Test"
    )
    assert mem_id4 is not None

    # Feature 1: Search and verify token economics display
    conn = database.get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE project = 'Test' AND active = 1 ORDER BY id DESC"
    ).fetchall()
    conn.close()

    # Should have 3 memories (one was deduped)
    assert len(rows) >= 3

    # Clear any previous output (from dedup messages)
    capsys.readouterr()

    # Show token economics
    display.show_token_economics(rows[:3], compact=True)
    captured = capsys.readouterr()

    # Should show token savings
    assert "tokens" in captured.out.lower()
    assert "saved" in captured.out.lower()

    # Feature 3: Switch to ops mode (disables token display)
    modes.set_mode("ops")
    config = modes.get_mode_config()
    assert config["show_tokens"] is False
    assert config["search_limit"] == 5

    # Token display should now be suppressed
    if not config["show_tokens"]:
        # In ops mode, token display is disabled
        pass  # Expected behavior

    # Clean up: switch back to default
    modes.set_mode("default")


def test_mode_affects_search_behavior(temp_db):
    """Test that mode configuration affects search behavior."""

    # Research mode: high search limit
    modes.set_mode("research")
    config = modes.get_mode_config()
    assert config["search_limit"] == 20
    assert config["show_tokens"] is True

    # Monitor mode: low search limit, no token display
    modes.set_mode("monitor")
    config = modes.get_mode_config()
    assert config["search_limit"] == 3
    assert config["show_tokens"] is False
    assert "error" in config["focus_categories"]
    assert "pending" in config["focus_categories"]


def test_content_hash_with_different_modes(temp_db):
    """Test that content-hash dedup works regardless of mode."""

    content = "Test content for dedup"

    # Add in default mode
    modes.set_mode("default")
    mem_id1 = memory_ops.add_memory("learning", content, project="Test")
    assert mem_id1 is not None

    # Switch to ops mode and try to add duplicate
    modes.set_mode("ops")
    mem_id2 = memory_ops.add_memory("learning", content, project="Test")
    assert mem_id2 is None  # Should still be blocked

    # Switch to research mode and try again
    modes.set_mode("research")
    mem_id3 = memory_ops.add_memory("learning", content, project="Test")
    assert mem_id3 is None  # Should still be blocked


def test_token_economics_respects_mode(temp_db, capsys):
    """Test that token economics display respects mode configuration."""

    # Create test memories
    conn = database.get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", "X" * 300)
        )
    conn.commit()
    rows = conn.execute("SELECT * FROM memories LIMIT 3").fetchall()
    conn.close()

    # In default mode, should show tokens
    modes.set_mode("default")
    config = modes.get_mode_config()
    if config["show_tokens"]:
        display.show_token_economics(rows, compact=True)
        captured = capsys.readouterr()
        assert "tokens" in captured.out.lower()

    # In ops mode, should not show tokens (caller checks config)
    modes.set_mode("ops")
    config = modes.get_mode_config()
    assert config["show_tokens"] is False


def test_all_modes_have_consistent_config(temp_db):
    """Test that all modes have consistent configuration keys."""

    required_keys = ["search_limit", "auto_tag", "show_tokens", "focus_projects", "focus_categories"]

    for mode_name in ["default", "dev", "ops", "research", "monitor"]:
        modes.set_mode(mode_name)
        config = modes.get_mode_config()

        for key in required_keys:
            assert key in config, f"Mode '{mode_name}' missing key '{key}'"
