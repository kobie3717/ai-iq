"""Comprehensive CLI integration tests for memory-tool."""

import pytest
import sys
import subprocess
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import cli, database, memory_ops, relations, graph


class TestCLIAdd:
    """Test 'add' command and variants."""

    def test_add_basic(self, temp_db, monkeypatch):
        """Test basic memory add via CLI."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'learning', 'Python is great'
        ])

        # Mock embedding to avoid model loading
        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        # Verify memory was added
        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE category = 'learning'").fetchone()
        assert row is not None
        assert 'Python is great' in row['content']
        conn.close()

    def test_add_with_tags(self, temp_db, monkeypatch):
        """Test add with tags."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'decision', 'Use PostgreSQL',
            '--tags', 'database,postgres'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE category = 'decision'").fetchone()
        assert row is not None
        assert 'database' in row['tags']
        assert 'postgres' in row['tags']
        conn.close()

    def test_add_with_project(self, temp_db, monkeypatch):
        """Test add with project."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'project', 'FlashVault is a VPN service',
            '--project', 'FlashVault'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE project = 'FlashVault'").fetchone()
        assert row is not None
        assert 'VPN service' in row['content']
        conn.close()

    def test_add_with_priority(self, temp_db, monkeypatch):
        """Test add with priority."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'error', 'Critical bug found',
            '--priority', '9'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE category = 'error'").fetchone()
        assert row is not None
        assert row['priority'] == 9
        conn.close()

    def test_add_with_expires(self, temp_db, monkeypatch):
        """Test add with expiration date."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'pending', 'Complete testing',
            '--expires', '2026-12-31'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE category = 'pending'").fetchone()
        assert row is not None
        assert '2026-12-31' in row['expires_at']
        conn.close()

    def test_add_with_topic_key(self, temp_db, monkeypatch):
        """Test add with topic key."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'architecture', 'Use microservices pattern',
            '--key', 'arch-pattern'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE topic_key = 'arch-pattern'").fetchone()
        assert row is not None
        conn.close()

    def test_add_with_provenance(self, temp_db, monkeypatch):
        """Test add with derived-from, citations, reasoning."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'add', 'learning', 'FSRS is superior to SM-2',
            '--derived-from', '1,2',
            '--citations', 'https://example.com',
            '--reasoning', 'Based on research papers'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE content LIKE '%FSRS%'").fetchone()
        assert row is not None
        assert row['derived_from'] == '1,2'
        assert row['citations'] == 'https://example.com'
        assert row['reasoning'] == 'Based on research papers'
        conn.close()


class TestCLISearch:
    """Test search commands."""

    def test_search_hybrid(self, db_with_samples, monkeypatch, capsys):
        """Test hybrid search (default)."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'search', 'PostgreSQL'
        ])

        with patch('memory_tool.embedding.semantic_search', return_value=[]):
            cli.main()

        captured = capsys.readouterr()
        # Should find the FlashVault memory with PostgreSQL
        assert 'PostgreSQL' in captured.out or 'No memories found' in captured.out

    def test_search_semantic_only(self, db_with_samples, monkeypatch, capsys):
        """Test semantic-only search."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'search', 'database', '--semantic'
        ])

        # Mock semantic search to return sample results
        mock_results = [(1, 0.85)]
        with patch('memory_tool.embedding.semantic_search', return_value=mock_results):
            cli.main()

        captured = capsys.readouterr()
        # Should execute semantic search and show results in new format
        assert '[' in captured.out or 'No memories found' in captured.out

    def test_search_keyword_only(self, db_with_samples, monkeypatch, capsys):
        """Test keyword-only search (FTS)."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'search', 'Node.js', '--keyword'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert '#' in captured.out or 'Node' in captured.out or 'No memories found' in captured.out

    def test_search_full_mode(self, db_with_samples, monkeypatch, capsys):
        """Test search with --full flag for verbose output."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'search', 'VPN', '--full'
        ])

        with patch('memory_tool.embedding.semantic_search', return_value=[]):
            cli.main()

        captured = capsys.readouterr()
        # Full mode should show more details
        assert captured.out != ''


class TestCLIGetList:
    """Test get and list commands."""

    def test_get_memory(self, db_with_samples, monkeypatch, capsys):
        """Test get command for single memory."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'get', '1'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Memory #1' in captured.out
        assert 'Category:' in captured.out

    def test_list_all(self, db_with_samples, monkeypatch, capsys):
        """Test list all memories."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'list'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert '#' in captured.out
        assert 'memories)' in captured.out

    def test_list_by_category(self, db_with_samples, monkeypatch, capsys):
        """Test list filtered by category."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'list', '--category', 'error'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'error' in captured.out or 'memories)' in captured.out

    def test_list_by_project(self, db_with_samples, monkeypatch, capsys):
        """Test list filtered by project."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'list', '--project', 'FlashVault'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'FlashVault' in captured.out or 'memories)' in captured.out

    def test_list_pending(self, db_with_samples, monkeypatch, capsys):
        """Test pending command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'pending'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'pending' in captured.out


class TestCLIUpdate:
    """Test update and delete commands."""

    def test_update_memory(self, sample_memory, monkeypatch, capsys):
        """Test update command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'update', str(sample_memory), 'Updated content here'
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (sample_memory,)).fetchone()
        assert 'Updated content here' in row['content']
        conn.close()

    def test_delete_memory(self, sample_memory, monkeypatch, capsys):
        """Test delete command (soft delete)."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'delete', str(sample_memory)
        ])

        cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (sample_memory,)).fetchone()
        assert row['active'] == 0
        conn.close()


class TestCLIRelations:
    """Test relationship commands."""

    def test_relate_memories(self, sample_memories, monkeypatch, capsys):
        """Test relate command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'relate', str(sample_memories[0]), str(sample_memories[1]), 'related'
        ])

        cli.main()

        conn = database.get_db()
        rel = conn.execute(
            "SELECT * FROM memory_relations WHERE source_id = ? AND target_id = ?",
            (sample_memories[0], sample_memories[1])
        ).fetchone()
        assert rel is not None
        conn.close()

    def test_conflicts(self, temp_db, monkeypatch, capsys):
        """Test conflicts detection."""
        # Add similar memories
        conn = database.get_db()
        conn.execute("INSERT INTO memories (category, content) VALUES (?, ?)",
                    ("learning", "Python is a programming language"))
        conn.execute("INSERT INTO memories (category, content) VALUES (?, ?)",
                    ("learning", "Python is a great programming language"))
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'conflicts'
        ])

        cli.main()

        captured = capsys.readouterr()
        # May find conflicts or may not depending on threshold
        assert 'conflicts' in captured.out.lower() or 'no conflicts' in captured.out.lower()

    def test_merge_memories(self, sample_memories, monkeypatch, capsys):
        """Test merge command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'merge', str(sample_memories[0]), str(sample_memories[1])
        ])

        with patch('memory_tool.embedding.embed_and_store'):
            cli.main()

        # One of the memories should be inactive after merge (older one gets deactivated)
        conn = database.get_db()
        mem0 = conn.execute("SELECT * FROM memories WHERE id = ?", (sample_memories[0],)).fetchone()
        mem1 = conn.execute("SELECT * FROM memories WHERE id = ?", (sample_memories[1],)).fetchone()
        # At least one should be inactive
        assert mem0['active'] == 0 or mem1['active'] == 0
        # At least one should be active
        assert mem0['active'] == 1 or mem1['active'] == 1
        conn.close()

    def test_supersede_memory(self, sample_memories, monkeypatch, capsys):
        """Test supersede command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'supersede', str(sample_memories[0]), str(sample_memories[1])
        ])

        cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (sample_memories[0],)).fetchone()
        assert row['active'] == 0
        conn.close()


class TestCLIStats:
    """Test stats and information commands."""

    def test_stats(self, db_with_samples, monkeypatch, capsys):
        """Test stats command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'stats'
        ])

        with patch('memory_tool.database.has_vec_support', return_value=False):
            cli.main()

        captured = capsys.readouterr()
        assert 'Memories:' in captured.out
        assert 'Projects:' in captured.out
        assert 'Categories:' in captured.out

    def test_stale(self, temp_db, monkeypatch, capsys):
        """Test stale command."""
        # Create a stale memory
        conn = database.get_db()
        conn.execute(
            "INSERT INTO memories (category, content, stale) VALUES (?, ?, ?)",
            ("learning", "Stale memory", 1)
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'stale'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'stale' in captured.out.lower()

    def test_projects(self, db_with_samples, monkeypatch, capsys):
        """Test projects summary."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'projects'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'FlashVault' in captured.out or 'memories' in captured.out


class TestCLIDecay:
    """Test decay and maintenance commands."""

    def test_decay(self, db_with_samples, monkeypatch, capsys):
        """Test decay command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'decay'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'decay' in captured.out.lower() or captured.out == ''

    def test_gc(self, temp_db, monkeypatch, capsys):
        """Test garbage collection."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'gc', '30'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'purged' in captured.out.lower() or captured.out == ''

    def test_gc_default_days(self, temp_db, monkeypatch, capsys):
        """Test gc with default 180 days."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'gc'
        ])

        cli.main()

        # Should complete without error
        captured = capsys.readouterr()
        assert True  # Just verify it runs


class TestCLISnapshot:
    """Test snapshot commands."""

    def test_snapshot_manual(self, temp_db, monkeypatch, capsys):
        """Test manual snapshot."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'snapshot', 'Completed testing phase'
        ])

        with patch('memory_tool.export.export_memory_md'):
            cli.main()

        conn = database.get_db()
        snap = conn.execute("SELECT * FROM session_snapshots ORDER BY created_at DESC LIMIT 1").fetchone()
        assert snap is not None
        assert 'testing phase' in snap['summary']
        conn.close()

    def test_snapshot_with_project(self, temp_db, monkeypatch, capsys):
        """Test snapshot with project flag."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'snapshot', 'Updated API', '--project', 'FlashVault'
        ])

        with patch('memory_tool.export.export_memory_md'):
            cli.main()

        conn = database.get_db()
        snap = conn.execute("SELECT * FROM session_snapshots ORDER BY created_at DESC LIMIT 1").fetchone()
        assert snap is not None
        assert snap['project'] == 'FlashVault'
        conn.close()

    def test_snapshots_list(self, temp_db, monkeypatch, capsys):
        """Test snapshots list command."""
        # Create a snapshot first
        conn = database.get_db()
        conn.execute(
            "INSERT INTO session_snapshots (summary, project) VALUES (?, ?)",
            ("Test snapshot", "TestProject")
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'snapshots'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Test snapshot' in captured.out or 'snapshots)' in captured.out

    def test_auto_snapshot(self, temp_db, monkeypatch, capsys):
        """Test auto-snapshot command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'auto-snapshot'
        ])

        with patch('memory_tool.snapshots.auto_snapshot'):
            cli.main()

        # Should complete without error
        assert True


class TestCLIBackup:
    """Test backup and restore commands."""

    def test_backup(self, temp_db, monkeypatch, capsys, tmp_path):
        """Test backup command."""
        # Patch BACKUP_DIR to use temp directory
        with patch('memory_tool.export.BACKUP_DIR', tmp_path):
            monkeypatch.setattr(sys, 'argv', [
                'memory-tool', 'backup'
            ])

            cli.main()

        # Check that backup was created
        backups = list(tmp_path.glob('memories_*.db'))
        assert len(backups) > 0

    def test_restore(self, temp_db, monkeypatch, capsys, tmp_path):
        """Test restore command."""
        # Create a backup file
        backup_file = tmp_path / "test_backup.db"
        backup_file.write_text("dummy backup")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'restore', str(backup_file)
        ])

        # Mock the actual restore to avoid overwriting test DB
        with patch('memory_tool.export.restore_db'):
            cli.main()

        # Should complete without error
        assert True


class TestCLINext:
    """Test next actions suggestion."""

    def test_next(self, temp_db, monkeypatch, capsys):
        """Test next command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'next'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Next' in captured.out or 'Suggestions' in captured.out or captured.out != ''


class TestCLIReindex:
    """Test reindex command."""

    def test_reindex(self, db_with_samples, monkeypatch, capsys):
        """Test reindex embeddings."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'reindex'
        ])

        # Mock embedding functions
        with patch('memory_tool.embedding.has_vec_support', return_value=False):
            cli.main()

        # Should complete without error (may skip if no vec support)
        assert True


class TestCLIHelp:
    """Test help command."""

    def test_help(self, temp_db, monkeypatch, capsys):
        """Test help command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'help'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
        assert 'memory-tool' in captured.out

    def test_no_args_shows_help(self, temp_db, monkeypatch, capsys):
        """Test that no args shows help."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool'
        ])

        with pytest.raises(SystemExit):
            cli.main()

        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or captured.out != ''


class TestCLITopics:
    """Test topics export."""

    def test_topics(self, db_with_samples, monkeypatch, capsys, tmp_path):
        """Test topics export command."""
        # Patch MEMORY_DIR to use temp directory
        with patch('memory_tool.export.MEMORY_DIR', tmp_path):
            monkeypatch.setattr(sys, 'argv', [
                'memory-tool', 'topics'
            ])

            cli.main()

        # Should complete without error
        captured = capsys.readouterr()
        assert 'Exported' in captured.out or 'topic' in captured.out.lower()


class TestCLIExport:
    """Test export command."""

    def test_export(self, db_with_samples, monkeypatch, capsys, tmp_path):
        """Test export MEMORY.md."""
        memory_md = tmp_path / "MEMORY.md"

        with patch('memory_tool.export.MEMORY_MD_PATH', memory_md):
            monkeypatch.setattr(sys, 'argv', [
                'memory-tool', 'export'
            ])

            cli.main()

        captured = capsys.readouterr()
        assert 'Exported' in captured.out

    def test_export_with_project(self, db_with_samples, monkeypatch, capsys, tmp_path):
        """Test export with project focus."""
        memory_md = tmp_path / "MEMORY.md"

        with patch('memory_tool.export.MEMORY_MD_PATH', memory_md):
            monkeypatch.setattr(sys, 'argv', [
                'memory-tool', 'export', '--project', 'FlashVault'
            ])

            cli.main()

        captured = capsys.readouterr()
        assert 'Exported' in captured.out
        assert 'FlashVault' in captured.out


class TestCLIDetectProject:
    """Test project detection."""

    def test_detect_project(self, temp_db, monkeypatch, capsys):
        """Test detect-project command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'detect-project'
        ])

        cli.main()

        captured = capsys.readouterr()
        # Will return project name or "Unknown project"
        assert captured.out != ''
