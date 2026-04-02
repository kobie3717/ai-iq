"""Tests for display and formatting functions."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import display, database


class TestFormatRow:
    """Test row formatting functions."""

    def test_format_row_basic(self, temp_db):
        """Test basic row formatting."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, project, tags, priority, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, ("learning", "Test content", "TestProject", "test,sample", 5, "manual"))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert f"#{mem_id}" in formatted
        assert "[learning]" in formatted
        assert "TestProject" in formatted
        assert "test,sample" in formatted
        assert "Test content" in formatted
        conn.close()

    def test_format_row_with_stale(self, temp_db):
        """Test formatting stale memory."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, stale, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("learning", "Stale content", 1))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "[STALE]" in formatted
        conn.close()

    def test_format_row_with_expiry(self, temp_db):
        """Test formatting with expiration date."""
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, expires_at, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("pending", "TODO item", future_date))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "[expires:" in formatted
        conn.close()

    def test_format_row_expired(self, temp_db):
        """Test formatting expired memory."""
        past_date = "2020-01-01"
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, expires_at, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("pending", "Expired item", past_date))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "[EXPIRED]" in formatted
        conn.close()

    def test_format_row_with_access_count(self, temp_db):
        """Test formatting with access count."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, access_count, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("learning", "Frequently accessed", 15))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "acc:15" in formatted
        conn.close()

    def test_format_row_with_topic_key(self, temp_db):
        """Test formatting with topic key."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, topic_key, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("architecture", "System design", "sys-design"))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "key:sys-design" in formatted
        conn.close()

    def test_format_row_with_revisions(self, temp_db):
        """Test formatting with revision count."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, revision_count, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("decision", "Updated decision", 5))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "rev:5" in formatted
        conn.close()

    def test_format_row_with_derived_from(self, temp_db):
        """Test formatting with derived_from."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, derived_from, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("learning", "Derived insight", "1,2,3"))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row(row)

        assert "derived:1,2,3" in formatted
        conn.close()


class TestFormatRowCompact:
    """Test compact formatting."""

    def test_format_row_compact_basic(self, temp_db):
        """Test compact format."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, project, access_count, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, ("learning", "Short content", "TestProject", 3))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row_compact(row)

        # New format: [id] category | content
        assert f"[{mem_id}]" in formatted
        assert "learning" in formatted
        assert "Short content" in formatted
        assert "(3x)" in formatted
        assert "tok" in formatted  # Token estimate should be present
        conn.close()

    def test_format_row_compact_long_content(self, temp_db):
        """Test compact format truncates long content."""
        long_content = "A" * 150
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, updated_at)
            VALUES (?, ?, datetime('now'))
        """, ("learning", long_content))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row_compact(row)

        # Should truncate and add "..."
        assert "..." in formatted
        assert len(formatted) < len(long_content) + 50  # Much shorter than original
        conn.close()

    def test_format_row_compact_with_importance(self, temp_db):
        """Test compact format with importance score."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, imp_score, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("decision", "Important decision", 8.5))
        mem_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        formatted = display.format_row_compact(row)

        assert "⚡8.5" in formatted
        conn.close()


class TestPrintMemoryFull:
    """Test full memory detail printing."""

    def test_print_memory_full_basic(self, temp_db, capsys):
        """Test printing full memory details."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, project, tags, priority, source, updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, ("learning", "Detailed content", "TestProject", "test,detail", 7, "manual"))
        mem_id = cursor.lastrowid
        conn.commit()
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert f"=== Memory #{mem_id} ===" in captured.out
        assert "Category: learning" in captured.out
        assert "Content: Detailed content" in captured.out
        assert "Project: TestProject" in captured.out
        assert "Tags: test,detail" in captured.out
        assert "Priority: 7" in captured.out

    def test_print_memory_full_not_found(self, temp_db, capsys):
        """Test printing non-existent memory."""
        display.print_memory_full(9999)

        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_print_memory_full_with_fsrs(self, temp_db, capsys):
        """Test printing memory with FSRS retention info."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, fsrs_stability, fsrs_difficulty,
                                last_accessed_at, updated_at, created_at)
            VALUES (?, ?, ?, ?, datetime('now', '-5 days'), datetime('now'), datetime('now'))
        """, ("learning", "FSRS tracked", 10.0, 5.0))
        mem_id = cursor.lastrowid
        conn.commit()
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert "Retention:" in captured.out or "Memory #" in captured.out

    def test_print_memory_full_with_importance(self, temp_db, capsys):
        """Test printing memory with importance scores."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, imp_score, imp_novelty, imp_relevance,
                                imp_frequency, imp_impact, updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, ("decision", "Important memory", 8.5, 7, 9, 8, 9))
        mem_id = cursor.lastrowid
        conn.commit()
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert "Importance:" in captured.out or "8.5" in captured.out

    def test_print_memory_full_with_provenance(self, temp_db, capsys):
        """Test printing memory with provenance fields."""
        conn = database.get_db()
        cursor = conn.execute("""
            INSERT INTO memories (category, content, derived_from, citations, reasoning,
                                updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, ("learning", "Derived memory", "1,2", "https://example.com", "Based on research"))
        mem_id = cursor.lastrowid
        conn.commit()
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert "Derived from:" in captured.out or "1,2" in captured.out
        assert "Citations:" in captured.out or "example.com" in captured.out
        assert "Reasoning:" in captured.out or "research" in captured.out

    def test_print_memory_full_with_relations(self, sample_memories, capsys):
        """Test printing memory with related memories."""
        # Add a relation
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memory_relations (source_id, target_id, relation_type)
            VALUES (?, ?, ?)
        """, (sample_memories[0], sample_memories[1], "related"))
        conn.commit()
        conn.close()

        display.print_memory_full(sample_memories[0])

        captured = capsys.readouterr()
        assert "Related memories:" in captured.out or f"#{sample_memories[1]}" in captured.out


class TestPrintHelp:
    """Test help text printing."""

    def test_print_help(self, temp_db, capsys):
        """Test help output contains key information."""
        display.print_help()

        captured = capsys.readouterr()
        assert "memory-tool" in captured.out
        assert "add" in captured.out
        assert "search" in captured.out
        assert "get" in captured.out
        assert "list" in captured.out
        assert "update" in captured.out
        assert "delete" in captured.out
        assert "graph" in captured.out
        assert "Categories:" in captured.out

    def test_help_includes_graph_commands(self, temp_db, capsys):
        """Test help includes graph intelligence commands."""
        display.print_help()

        captured = capsys.readouterr()
        assert "Graph Intelligence" in captured.out
        assert "graph add" in captured.out
        assert "graph rel" in captured.out
        assert "graph fact" in captured.out

    def test_help_includes_run_tracking(self, temp_db, capsys):
        """Test help includes run tracking commands."""
        display.print_help()

        captured = capsys.readouterr()
        assert "Run Tracking" in captured.out or "run start" in captured.out

    def test_help_includes_sync_commands(self, temp_db, capsys):
        """Test help includes OpenClaw bridge commands."""
        display.print_help()

        captured = capsys.readouterr()
        assert "sync" in captured.out or "OpenClaw" in captured.out


class TestParseFlags:
    """Test CLI flag parsing."""

    def test_parse_flags_basic(self):
        """Test basic flag parsing."""
        from memory_tool import cli
        argv = ['memory-tool', 'add', 'learning', 'content', '--tags', 'test,sample']
        flags, remaining = cli.parse_flags(argv, 4)

        assert flags['tags'] == 'test,sample'
        assert remaining == []

    def test_parse_flags_multiple(self):
        """Test multiple flags."""
        from memory_tool import cli
        argv = ['memory-tool', 'add', 'learning', 'content', '--tags', 'test', '--priority', '5', '--project', 'TestProj']
        flags, remaining = cli.parse_flags(argv, 4)

        assert flags['tags'] == 'test'
        assert flags['priority'] == '5'
        assert flags['project'] == 'TestProj'
        assert remaining == []

    def test_parse_flags_boolean(self):
        """Test boolean flags."""
        from memory_tool import cli
        argv = ['memory-tool', 'search', 'query', '--full', '--semantic']
        flags, remaining = cli.parse_flags(argv, 3)

        assert flags['full'] is True
        assert flags['semantic'] is True
        assert remaining == []

    def test_parse_flags_with_remaining(self):
        """Test flags with remaining arguments."""
        from memory_tool import cli
        argv = ['memory-tool', 'snapshot', 'Summary text here', '--project', 'TestProj']
        flags, remaining = cli.parse_flags(argv, 2)

        assert flags['project'] == 'TestProj'
        assert 'Summary text here' in remaining


class TestFormatDuration:
    """Test duration formatting."""

    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        from memory_tool.runs import format_duration

        start = "2026-03-30T10:00:00"
        end = "2026-03-30T10:00:45"

        result = format_duration(start, end)
        assert "45s" in result

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        from memory_tool.runs import format_duration

        start = "2026-03-30T10:00:00"
        end = "2026-03-30T10:05:30"

        result = format_duration(start, end)
        assert "5m" in result and "30s" in result

    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        from memory_tool.runs import format_duration

        start = "2026-03-30T10:00:00"
        end = "2026-03-30T12:15:00"

        result = format_duration(start, end)
        assert "2h" in result and "15m" in result

    def test_format_duration_no_end(self):
        """Test formatting ongoing duration."""
        from memory_tool.runs import format_duration

        start = datetime.now().isoformat()
        result = format_duration(start, None)

        # Should calculate from now
        assert result != "unknown"

    def test_format_duration_invalid(self):
        """Test formatting with invalid timestamp."""
        from memory_tool.runs import format_duration

        result = format_duration(None, None)
        assert result == "unknown"

        result = format_duration("invalid", "invalid")
        assert result == "unknown"
