"""Tests for search feedback tracking and learning system."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import add_memory, search_memories
from memory_tool.feedback import (
    log_search_feedback, get_search_quality_stats, apply_feedback_learning,
    log_usage, log_miss, get_improvement_suggestions, auto_feedback_from_session
)
from memory_tool.config import DB_PATH


@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_memories.db"
    monkeypatch.setattr("memory_tool.config.DB_PATH", temp_db_path)
    monkeypatch.setattr("memory_tool.database.DB_PATH", temp_db_path)
    monkeypatch.setattr("memory_tool.memory_ops.DB_PATH", temp_db_path)
    init_db()
    yield temp_db_path
    # Cleanup
    if temp_db_path.exists():
        temp_db_path.unlink()


def test_search_logging(temp_db, capsys):
    """Test that searches are logged to search_log table."""
    # Add some test memories
    add_memory("learning", "Python async/await patterns", skip_dedup=True)
    add_memory("learning", "FastAPI best practices", skip_dedup=True)
    add_memory("decision", "Use pytest for testing", skip_dedup=True)

    # Perform a search
    results, search_id, _ = search_memories("python", mode="keyword")

    # Verify search was logged
    conn = get_db()
    log_entry = conn.execute("SELECT * FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    assert log_entry is not None
    assert log_entry['query'] == "python"
    assert log_entry['search_type'] == "keyword"
    assert log_entry['result_count'] > 0
    assert log_entry['result_ids'] is not None
    assert log_entry['latency_ms'] >= 0


def test_feedback_logging(temp_db, capsys):
    """Test logging feedback for which results were used."""
    # Add test memories
    mem1 = add_memory("learning", "Docker container best practices", skip_dedup=True)
    mem2 = add_memory("learning", "Docker compose configurations", skip_dedup=True)
    mem3 = add_memory("learning", "Kubernetes deployment", skip_dedup=True)

    # Search
    results, search_id, _ = search_memories("docker", mode="keyword")

    # Mark only mem1 and mem2 as used
    log_search_feedback(search_id, [mem1, mem2])

    # Verify feedback was logged
    conn = get_db()
    log_entry = conn.execute("SELECT * FROM search_log WHERE id = ?", (search_id,)).fetchone()

    assert log_entry['used_ids'] is not None
    assert str(mem1) in log_entry['used_ids']
    assert str(mem2) in log_entry['used_ids']

    # Hit rate should be calculated (2 used out of total results)
    result_count = len(log_entry['result_ids'].split(',')) if log_entry['result_ids'] else 0
    if result_count > 0:
        expected_rate = 2 / result_count
        assert abs(log_entry['hit_rate'] - expected_rate) < 0.01

    # Used memories should have increased access_count
    mem1_row = conn.execute("SELECT access_count FROM memories WHERE id = ?", (mem1,)).fetchone()
    assert mem1_row['access_count'] >= 2  # Initial touch + feedback boost

    conn.close()


def test_search_quality_stats(temp_db, capsys):
    """Test getting search quality statistics."""
    # Add test memories
    mem1 = add_memory("learning", "React hooks patterns", skip_dedup=True)
    mem2 = add_memory("learning", "React state management", skip_dedup=True)
    mem3 = add_memory("learning", "Vue.js components", skip_dedup=True)

    # Perform multiple searches with feedback
    results1, sid1, _ = search_memories("react", mode="keyword")
    log_search_feedback(sid1, [mem1, mem2])  # 100% hit rate (if both returned)

    results2, sid2, _ = search_memories("vue", mode="keyword")
    log_search_feedback(sid2, [])  # 0% hit rate

    # Get stats
    stats = get_search_quality_stats()

    # Verify stats structure
    assert 'hit_rate_7d' in stats
    assert 'hit_rate_30d' in stats
    assert 'hit_rate_all' in stats
    assert 'search_patterns' in stats
    assert 'failing_queries' in stats

    # Should have some searches recorded
    assert stats['hit_rate_all']['searches'] >= 2


def test_apply_feedback_learning(temp_db, capsys):
    """Test that feedback learning adjusts memory priorities."""
    # Add test memories with initial priorities
    mem1 = add_memory("learning", "High value memory", skip_dedup=True, priority=5)
    mem2 = add_memory("learning", "Low value memory", skip_dedup=True, priority=5)
    mem3 = add_memory("learning", "Never used memory", skip_dedup=True, priority=5)

    conn = get_db()

    # Simulate high-value memory: retrieved and used 12 times
    for i in range(12):
        cur = conn.execute("""
            INSERT INTO search_log (query, search_type, result_ids, result_count, used_ids, hit_rate)
            VALUES (?, 'keyword', ?, 1, ?, 1.0)
        """, (f"query{i}", str(mem1), str(mem1)))

    # Simulate low-value memory: retrieved 12 times, used only once
    for i in range(12):
        used = str(mem2) if i == 0 else ""
        hit_rate = 1.0 if i == 0 else 0.0
        cur = conn.execute("""
            INSERT INTO search_log (query, search_type, result_ids, result_count, used_ids, hit_rate)
            VALUES (?, 'keyword', ?, 1, ?, ?)
        """, (f"low{i}", str(mem2), used, hit_rate))

    # Simulate never-used memory: retrieved 25 times, never used
    for i in range(25):
        cur = conn.execute("""
            INSERT INTO search_log (query, search_type, result_ids, result_count, used_ids, hit_rate)
            VALUES (?, 'keyword', ?, 1, '', 0.0)
        """, (f"unused{i}", str(mem3)))

    conn.commit()

    # Get initial priorities
    mem1_before = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem1,)).fetchone()
    mem2_before = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem2,)).fetchone()
    mem3_before = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem3,)).fetchone()

    # Apply feedback learning
    results = apply_feedback_learning(conn)

    # Get final priorities
    mem1_after = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem1,)).fetchone()
    mem2_after = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem2,)).fetchone()
    mem3_after = conn.execute("SELECT priority, stale FROM memories WHERE id = ?", (mem3,)).fetchone()

    conn.close()

    # Verify learning was applied
    assert results['boosted'] >= 1  # mem1 should be boosted
    assert results['decayed'] >= 1  # mem2 should be decayed
    assert results['flagged'] >= 1  # mem3 should be flagged as stale

    # High-value memory should have increased priority
    assert mem1_after['priority'] > mem1_before['priority']

    # Low-value memory should have decreased priority
    assert mem2_after['priority'] < mem2_before['priority']

    # Never-used memory should be flagged as stale
    assert mem3_after['stale'] == 1


def test_hit_rate_calculation(temp_db, capsys):
    """Test that hit rate is correctly calculated."""
    # Add memories
    mem1 = add_memory("learning", "Memory A", skip_dedup=True)
    mem2 = add_memory("learning", "Memory B", skip_dedup=True)
    mem3 = add_memory("learning", "Memory C", skip_dedup=True)

    # Search that returns all 3
    results, search_id, _ = search_memories("memory", mode="keyword")

    # Only use 2 out of 3
    log_search_feedback(search_id, [mem1, mem2])

    # Verify hit rate
    conn = get_db()
    log_entry = conn.execute("SELECT hit_rate, result_count FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    # Hit rate should be approximately 2/3 = 0.67
    if log_entry['result_count'] >= 2:
        expected_rate = 2 / log_entry['result_count']
        assert abs(log_entry['hit_rate'] - expected_rate) < 0.1


def test_no_results_search(temp_db, capsys):
    """Test that searches with no results are handled gracefully."""
    results, search_id, _ = search_memories("nonexistent query xyz", mode="keyword")

    # Should return empty results
    assert len(results) == 0

    # Should still be logged
    conn = get_db()
    log_entry = conn.execute("SELECT * FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    assert log_entry is not None
    assert log_entry['result_count'] == 0


def test_feedback_with_invalid_search_id(temp_db, capsys):
    """Test that feedback with invalid search_id is handled gracefully."""
    # Should not crash
    log_search_feedback(99999, [1, 2, 3])

    # Should log a warning (captured output will have warning message)
    captured = capsys.readouterr()
    # No assertion needed - just verify it doesn't crash


def test_empty_feedback(temp_db, capsys):
    """Test logging feedback with empty used_ids list."""
    mem1 = add_memory("learning", "Test memory", skip_dedup=True)
    results, search_id, _ = search_memories("test", mode="keyword")

    # Log empty feedback (nothing was used)
    log_search_feedback(search_id, [])

    conn = get_db()
    log_entry = conn.execute("SELECT hit_rate FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    # Hit rate should be 0
    assert log_entry['hit_rate'] == 0.0


def test_search_modes_logged(temp_db, capsys):
    """Test that different search modes are properly logged."""
    add_memory("learning", "Test content", skip_dedup=True)

    # Test each mode
    results_hybrid, sid_hybrid, _ = search_memories("test", mode="hybrid")
    results_keyword, sid_keyword, _ = search_memories("test", mode="keyword")
    # Semantic mode requires embeddings, skip if not available

    conn = get_db()
    log_hybrid = conn.execute("SELECT search_type FROM search_log WHERE id = ?", (sid_hybrid,)).fetchone()
    log_keyword = conn.execute("SELECT search_type FROM search_log WHERE id = ?", (sid_keyword,)).fetchone()
    conn.close()

    assert log_hybrid['search_type'] == "hybrid"
    assert log_keyword['search_type'] == "keyword"


def test_log_usage(temp_db, capsys):
    """Test logging individual memory usage."""
    mem1 = add_memory("learning", "Test memory 1", skip_dedup=True)
    results, search_id, _ = search_memories("test", mode="keyword")

    conn = get_db()

    # Log usage for mem1
    log_usage(conn, mem1, search_id, 'retrieved')

    # Verify it was logged
    log_entry = conn.execute("SELECT used_ids, hit_rate FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    assert str(mem1) in log_entry['used_ids']
    assert log_entry['hit_rate'] > 0


def test_log_miss(temp_db, capsys):
    """Test logging search misses (knowledge gaps)."""
    conn = get_db()

    # Log a miss
    log_miss(conn, "non-existent query", "no_results")

    # Verify miss was logged
    searches = conn.execute("""
        SELECT * FROM search_log WHERE query = 'non-existent query'
    """).fetchall()
    conn.close()

    assert len(searches) == 1
    assert searches[0]['result_count'] == 0
    assert searches[0]['hit_rate'] == 0.0


def test_get_improvement_suggestions(temp_db, capsys):
    """Test getting improvement suggestions."""
    # Create a memory that will be retrieved often but never used
    mem1 = add_memory("learning", "Frequently retrieved but never used", skip_dedup=True, priority=5)

    conn = get_db()

    # Create search logs: retrieved 6 times, never used
    for i in range(6):
        conn.execute("""
            INSERT INTO search_log (query, search_type, result_ids, result_count, used_ids, hit_rate)
            VALUES (?, 'hybrid', ?, 1, '', 0.0)
        """, (f"query{i}", str(mem1)))

    # Add some knowledge gaps
    conn.execute("""
        INSERT INTO search_log (query, search_type, result_count, hit_rate)
        VALUES ('missing knowledge', 'hybrid', 0, 0.0)
    """)

    conn.commit()

    # Get suggestions
    suggestions = get_improvement_suggestions(conn)
    conn.close()

    # Verify suggestions structure
    assert 'deprecation_candidates' in suggestions
    assert 'knowledge_gaps' in suggestions
    assert 'tag_suggestions' in suggestions

    # Should suggest deprecating mem1
    dep_candidates = [c['id'] for c in suggestions['deprecation_candidates']]
    assert mem1 in dep_candidates

    # Should identify knowledge gap
    gaps = [g['query'] for g in suggestions['knowledge_gaps']]
    assert 'missing knowledge' in gaps


def test_auto_feedback_from_session(temp_db, capsys):
    """Test parsing session transcripts for feedback."""
    import json
    mem1 = add_memory("learning", "Test memory for transcript", skip_dedup=True)

    # Create a mock session transcript
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        # Search command
        json.dump({
            'type': 'tool_use',
            'name': 'search_memories',
            'input': {'query': 'test query'}
        }, f)
        f.write('\n')

        # Get command (usage signal)
        json.dump({
            'type': 'tool_use',
            'name': 'get_memory',
            'input': {'id': mem1}
        }, f)
        f.write('\n')

        transcript_path = f.name

    try:
        # Parse transcript
        stats = auto_feedback_from_session(transcript_path)

        # Verify stats
        assert stats['searches'] >= 1
        assert stats['uses'] >= 1

        # Verify search was logged
        conn = get_db()
        searches = conn.execute("SELECT * FROM search_log WHERE query = 'test query'").fetchall()
        conn.close()
        assert len(searches) >= 1

    finally:
        # Cleanup
        Path(transcript_path).unlink()


def test_improvement_suggestions_empty(temp_db, capsys):
    """Test improvement suggestions with no data."""
    conn = get_db()
    suggestions = get_improvement_suggestions(conn)
    conn.close()

    # Should return empty lists without crashing
    assert suggestions['deprecation_candidates'] == []
    assert suggestions['knowledge_gaps'] == []


def test_cli_feedback_stats(temp_db, capsys):
    """Test the feedback-stats CLI command."""
    from memory_tool.cli import main
    import sys

    # Add some test data
    mem1 = add_memory("learning", "Test memory for CLI", skip_dedup=True)
    results, search_id, _ = search_memories("test", mode="keyword")
    log_search_feedback(search_id, [mem1])

    # Run command
    sys.argv = ['memory-tool', 'feedback-stats']
    try:
        main()
    except SystemExit:
        pass  # Command may exit normally

    captured = capsys.readouterr()
    assert "Search Quality Report" in captured.out
    assert "Overall Hit Rates" in captured.out


def test_cli_gaps(temp_db, capsys):
    """Test the gaps CLI command."""
    from memory_tool.cli import main
    import sys

    # Create a knowledge gap
    conn = get_db()
    conn.execute("""
        INSERT INTO search_log (query, search_type, result_count, hit_rate)
        VALUES ('missing topic', 'keyword', 0, 0.0)
    """)
    conn.commit()
    conn.close()

    # Run command
    sys.argv = ['memory-tool', 'gaps']
    try:
        main()
    except SystemExit:
        pass

    captured = capsys.readouterr()
    assert "Knowledge Gaps" in captured.out
    assert "missing topic" in captured.out


def test_search_returns_search_id(temp_db, capsys):
    """Test that search command returns search_id in output."""
    mem1 = add_memory("learning", "Test memory", skip_dedup=True)
    results, search_id, _ = search_memories("test", mode="keyword")

    assert search_id is not None
    assert search_id > 0

    # Verify it's in the database
    conn = get_db()
    log_entry = conn.execute("SELECT * FROM search_log WHERE id = ?", (search_id,)).fetchone()
    conn.close()

    assert log_entry is not None
    assert log_entry['query'] == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
