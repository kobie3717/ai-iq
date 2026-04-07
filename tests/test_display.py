"""Tests for display formatting functions."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from io import StringIO

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import display, database


class TestFormatRow:
    """Test format_row function for verbose output."""

    def test_format_basic_memory(self, db_with_samples):
        """Test formatting a basic memory."""
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE active = 1 LIMIT 1").fetchone()
        conn.close()

        result = display.format_row(row)

        assert f"#{row['id']}" in result
        assert f"[{row['category']}]" in result
        assert row['content'] in result

    def test_format_with_tags(self, db_with_samples):
        """Test formatting memory with tags."""
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE tags != '' AND active = 1 LIMIT 1").fetchone()
        conn.close()

        if row:
            result = display.format_row(row)
            assert "tags:" in result

    def test_format_with_project(self, db_with_samples):
        """Test formatting memory with project."""
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE project IS NOT NULL AND active = 1 LIMIT 1").fetchone()
        conn.close()

        if row:
            result = display.format_row(row)
            assert "project:" in result
            assert row['project'] in result

    def test_format_stale_memory(self, temp_db):
        """Test formatting stale memory."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, stale, active)
            VALUES (?, ?, ?, ?)
        """, ("learning", "Stale memory", 1, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE stale = 1 AND active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "[STALE]" in result

    def test_format_with_expiry(self, temp_db):
        """Test formatting memory with expiration."""
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, expires_at, active)
            VALUES (?, ?, ?, ?)
        """, ("pending", "Expiring memory", future_date, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE expires_at IS NOT NULL AND active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "expires:" in result

    def test_format_expired_memory(self, temp_db):
        """Test formatting expired memory."""
        past_date = (datetime.now() - timedelta(days=30)).isoformat()
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, expires_at, active)
            VALUES (?, ?, ?, ?)
        """, ("pending", "Expired memory", past_date, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE expires_at IS NOT NULL AND active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "[EXPIRED]" in result

    def test_format_with_topic_key(self, temp_db):
        """Test formatting memory with topic key."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, topic_key, active)
            VALUES (?, ?, ?, ?)
        """, ("learning", "Memory with key", "test-key", 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE topic_key IS NOT NULL AND active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "key:" in result

    def test_format_with_access_count(self, temp_db):
        """Test formatting memory with access count."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, access_count, active)
            VALUES (?, ?, ?, ?)
        """, ("learning", "Accessed memory", 5, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE access_count > 0 AND active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "acc:" in result


class TestFormatRowCompact:
    """Test format_row_compact function."""

    def test_compact_basic(self, db_with_samples):
        """Test compact formatting."""
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE active = 1 LIMIT 1").fetchone()
        conn.close()

        result = display.format_row_compact(row)

        assert f"#{row['id']}" in result
        assert f"[{row['category']}]" in result
        # Content should be truncated to 100 chars
        assert len(result) < len(display.format_row(row))

    def test_compact_with_long_content(self, temp_db):
        """Test compact formatting with long content."""
        long_content = "A" * 150
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, active)
            VALUES (?, ?, ?)
        """, ("learning", long_content, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
        conn.close()

        result = display.format_row_compact(row)
        assert "..." in result  # Should have ellipsis for truncation

    def test_compact_with_project(self, db_with_samples):
        """Test compact formatting with project."""
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE project IS NOT NULL AND active = 1 LIMIT 1").fetchone()
        conn.close()

        if row:
            result = display.format_row_compact(row)
            assert "project:" in result

    def test_compact_with_access_count(self, temp_db):
        """Test compact formatting with access count."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, access_count, active)
            VALUES (?, ?, ?, ?)
        """, ("learning", "Popular memory", 10, 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE access_count > 0 AND active = 1").fetchone()
        conn.close()

        result = display.format_row_compact(row)
        assert "x)" in result  # Access count indicator


class TestPrintMemoryFull:
    """Test print_memory_full function."""

    def test_print_full_existing_memory(self, db_with_samples, capsys):
        """Test printing full memory details."""
        conn = database.get_db()
        mem_id = conn.execute("SELECT id FROM memories WHERE active = 1 LIMIT 1").fetchone()["id"]
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert f"Memory #{mem_id}" in captured.out
        assert "Category:" in captured.out
        assert "Content:" in captured.out
        assert "Priority:" in captured.out
        assert "Created:" in captured.out

    def test_print_full_nonexistent_memory(self, temp_db, capsys):
        """Test printing non-existent memory."""
        display.print_memory_full(99999)

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_print_full_with_tags(self, db_with_samples, capsys):
        """Test printing memory with tags."""
        conn = database.get_db()
        mem = conn.execute("SELECT id FROM memories WHERE tags != '' AND active = 1 LIMIT 1").fetchone()
        conn.close()

        if mem:
            display.print_memory_full(mem["id"])

            captured = capsys.readouterr()
            assert "Tags:" in captured.out

    def test_print_full_with_project(self, db_with_samples, capsys):
        """Test printing memory with project."""
        conn = database.get_db()
        mem = conn.execute("SELECT id FROM memories WHERE project IS NOT NULL AND active = 1 LIMIT 1").fetchone()
        conn.close()

        if mem:
            display.print_memory_full(mem["id"])

            captured = capsys.readouterr()
            assert "Project:" in captured.out

    def test_print_full_with_expiry(self, temp_db, capsys):
        """Test printing memory with expiration."""
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, expires_at, active)
            VALUES (?, ?, ?, ?)
        """, ("pending", "Will expire", future_date, 1))
        conn.commit()

        mem_id = conn.execute("SELECT id FROM memories WHERE active = 1 ORDER BY id DESC LIMIT 1").fetchone()["id"]
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert "Expires:" in captured.out

    def test_print_full_stale_memory(self, temp_db, capsys):
        """Test printing stale memory."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, stale, active)
            VALUES (?, ?, ?, ?)
        """, ("learning", "Stale memory", 1, 1))
        conn.commit()

        mem_id = conn.execute("SELECT id FROM memories WHERE stale = 1 AND active = 1").fetchone()["id"]
        conn.close()

        display.print_memory_full(mem_id)

        captured = capsys.readouterr()
        assert "STALE" in captured.out

    def test_print_full_with_related_memories(self, sample_memories, capsys):
        """Test printing memory with related memories."""
        mem1, mem2 = sample_memories[0], sample_memories[1]

        # Create a relationship
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memory_relations (source_id, target_id, relation_type)
            VALUES (?, ?, ?)
        """, (mem1, mem2, "related"))
        conn.commit()
        conn.close()

        display.print_memory_full(mem1)

        captured = capsys.readouterr()
        assert "Related memories:" in captured.out


class TestPrintHelp:
    """Test print_help function."""

    def test_help_output(self, capsys):
        """Test help text output."""
        display.print_help()

        captured = capsys.readouterr()
        assert "Memory System" in captured.out
        assert "Usage:" in captured.out
        assert "add" in captured.out
        assert "search" in captured.out
        assert "update" in captured.out
        assert "delete" in captured.out
        assert "Categories:" in captured.out

    def test_help_shows_all_commands(self, capsys):
        """Test that help shows all major commands."""
        display.print_help()

        captured = capsys.readouterr()
        commands = [
            "add", "search", "get", "list", "update", "delete",
            "relate", "conflicts", "merge", "supersede", "pending",
            "stats", "decay", "snapshot", "backup", "restore",
            "graph", "run", "dream", "next"
        ]

        for cmd in commands:
            assert cmd in captured.out

    def test_help_shows_graph_commands(self, capsys):
        """Test that help shows graph intelligence commands."""
        display.print_help()

        captured = capsys.readouterr()
        assert "Graph Intelligence" in captured.out
        assert "graph add" in captured.out
        assert "graph rel" in captured.out
        assert "graph fact" in captured.out

    def test_help_shows_run_commands(self, capsys):
        """Test that help shows run tracking commands."""
        display.print_help()

        captured = capsys.readouterr()
        assert "Run Tracking" in captured.out
        assert "run start" in captured.out
        assert "run complete" in captured.out


class TestFormatRowEdgeCases:
    """Test edge cases in format_row."""

    def test_format_minimal_memory(self, temp_db):
        """Test formatting memory with minimal fields."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, active)
            VALUES (?, ?, ?)
        """, ("learning", "Minimal", 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "Minimal" in result
        assert "[learning]" in result

    def test_format_with_all_fields(self, temp_db):
        """Test formatting memory with all possible fields."""
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (
                category, content, project, tags, priority,
                access_count, stale, expires_at, source,
                topic_key, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "learning", "Full memory", "TestProj", "tag1,tag2", 8,
            5, 1, future_date, "auto",
            "test-key", 1
        ))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "Full memory" in result
        assert "project:TestProj" in result
        assert "tags:" in result
        assert "acc:" in result
        assert "[STALE]" in result
        assert "expires:" in result
        assert "src:auto" in result
        assert "key:test-key" in result

    def test_format_with_unicode_content(self, temp_db):
        """Test formatting memory with Unicode characters."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, active)
            VALUES (?, ?, ?)
        """, ("learning", "Memory with émojis 🎉 and ümlauts", 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "émojis" in result or "moji" in result  # May be encoded differently

    def test_format_with_special_characters(self, temp_db):
        """Test formatting memory with special characters."""
        conn = database.get_db()
        conn.execute("""
            INSERT INTO memories (category, content, active)
            VALUES (?, ?, ?)
        """, ("learning", "Memory with <tags> & \"quotes\"", 1))
        conn.commit()

        row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
        conn.close()

        result = display.format_row(row)
        assert "<tags>" in result or "tags" in result
        assert "&" in result or "and" in result


class TestFormatRowWithProvenanceFields:
    """Test formatting with provenance fields (Phase 6)."""

    def test_format_with_derived_from(self, temp_db):
        """Test formatting memory with derived_from field if column exists."""
        conn = database.get_db()

        # Check if column exists
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]

        if "derived_from" in columns:
            conn.execute("""
                INSERT INTO memories (category, content, derived_from, active)
                VALUES (?, ?, ?, ?)
            """, ("learning", "Derived memory", "1,2,3", 1))
            conn.commit()

            row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()
            conn.close()

            result = display.format_row(row)
            assert "derived:" in result
        else:
            conn.close()
            # Column doesn't exist in this schema version, skip test
            pytest.skip("derived_from column not in schema")

    def test_format_with_citations(self, temp_db, capsys):
        """Test formatting memory with citations if column exists."""
        conn = database.get_db()

        # Check if column exists
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]

        if "citations" in columns:
            conn.execute("""
                INSERT INTO memories (category, content, citations, active)
                VALUES (?, ?, ?, ?)
            """, ("learning", "Memory with sources", "https://example.com;/path/file", 1))
            conn.commit()

            row = conn.execute("SELECT * FROM memories WHERE active = 1").fetchone()

            # Citations shown in full detail view
            display.print_memory_full(row["id"])

            captured = capsys.readouterr()
            assert "Citations:" in captured.out
            conn.close()
        else:
            conn.close()
            # Column doesn't exist in this schema version, skip test
            pytest.skip("citations column not in schema")
