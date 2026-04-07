"""CLI integration tests for graph intelligence commands."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import cli, database, graph


class TestGraphCLIBasic:
    """Test basic graph CLI commands."""

    def test_graph_summary(self, temp_db, monkeypatch, capsys):
        """Test 'graph' command shows summary."""
        monkeypatch.setattr(sys, 'argv', ['memory-tool', 'graph'])

        cli.main()

        captured = capsys.readouterr()
        assert 'Graph Intelligence Summary:' in captured.out
        assert 'Entities:' in captured.out
        assert 'Relationships:' in captured.out

    def test_graph_stats(self, temp_db, monkeypatch, capsys):
        """Test 'graph stats' command."""
        monkeypatch.setattr(sys, 'argv', ['memory-tool', 'graph', 'stats'])

        cli.main()

        captured = capsys.readouterr()
        assert 'Graph Statistics:' in captured.out
        assert 'Entities:' in captured.out


class TestGraphEntityCommands:
    """Test graph entity management commands."""

    def test_graph_add_entity(self, temp_db, monkeypatch, capsys):
        """Test adding an entity via CLI."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'add', 'person', 'Alice', 'Software developer'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Added entity' in captured.out
        assert 'Alice' in captured.out

        # Verify in database
        conn = database.get_db()
        entity = conn.execute(
            "SELECT * FROM graph_entities WHERE name = 'Alice'"
        ).fetchone()
        assert entity is not None
        assert entity['type'] == 'person'
        assert entity['summary'] == 'Software developer'
        conn.close()

    def test_graph_add_entity_minimal(self, temp_db, monkeypatch, capsys):
        """Test adding entity without summary."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'add', 'project', 'ProjectX'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Added entity' in captured.out

        conn = database.get_db()
        entity = conn.execute(
            "SELECT * FROM graph_entities WHERE name = 'ProjectX'"
        ).fetchone()
        assert entity is not None
        assert entity['type'] == 'project'
        conn.close()

    def test_graph_list_entities(self, sample_entities, monkeypatch, capsys):
        """Test listing all entities."""
        monkeypatch.setattr(sys, 'argv', ['memory-tool', 'graph', 'list'])

        cli.main()

        captured = capsys.readouterr()
        assert 'Alice' in captured.out
        assert 'Bob' in captured.out
        assert 'entities)' in captured.out

    def test_graph_list_entities_by_type(self, sample_entities, monkeypatch, capsys):
        """Test listing entities filtered by type."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'list', 'person'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Alice' in captured.out
        assert 'Bob' in captured.out

    def test_graph_get_entity(self, sample_entities, monkeypatch, capsys):
        """Test getting entity details."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'get', 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Alice' in captured.out
        assert 'person' in captured.out
        assert 'Importance:' in captured.out

    def test_graph_get_nonexistent_entity(self, temp_db, monkeypatch, capsys):
        """Test getting non-existent entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'get', 'NonExistent'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'not found' in captured.out

    def test_graph_delete_entity(self, sample_entities, monkeypatch, capsys):
        """Test deleting an entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'delete', 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Deleted entity' in captured.out

        # Verify deletion
        conn = database.get_db()
        entity = conn.execute(
            "SELECT * FROM graph_entities WHERE name = 'Alice'"
        ).fetchone()
        assert entity is None
        conn.close()


class TestGraphRelationshipCommands:
    """Test graph relationship commands."""

    def test_graph_add_relationship(self, sample_entities, monkeypatch, capsys):
        """Test adding a relationship."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'rel', 'Alice', 'works_on', 'ProjectX', 'Lead developer'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Added relationship' in captured.out
        assert 'Alice' in captured.out
        assert 'ProjectX' in captured.out

        # Verify in database
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        project_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'ProjectX'").fetchone()['id']

        rel = conn.execute("""
            SELECT * FROM graph_relationships
            WHERE from_entity_id = ? AND to_entity_id = ?
        """, (alice_id, project_id)).fetchone()

        assert rel is not None
        assert rel['relation_type'] == 'works_on'
        assert rel['note'] == 'Lead developer'
        conn.close()

    def test_graph_add_relationship_minimal(self, sample_entities, monkeypatch, capsys):
        """Test adding relationship without note."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'rel', 'Alice', 'knows', 'Bob'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Added relationship' in captured.out

    def test_graph_relationship_shown_in_get(self, sample_entities, monkeypatch, capsys):
        """Test relationships appear in entity get."""
        # Add a relationship
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        bob_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Bob'").fetchone()['id']
        conn.execute("""
            INSERT INTO graph_relationships (from_entity_id, to_entity_id, relation_type, note)
            VALUES (?, ?, ?, ?)
        """, (alice_id, bob_id, 'knows', 'Colleague'))
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'get', 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Relationships' in captured.out or 'knows' in captured.out


class TestGraphFactCommands:
    """Test graph fact commands."""

    def test_graph_add_fact(self, sample_entities, monkeypatch, capsys):
        """Test adding a fact to an entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'fact', 'Alice', 'email', 'alice@example.com'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Set fact' in captured.out
        assert 'Alice.email' in captured.out

        # Verify in database
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        fact = conn.execute("""
            SELECT * FROM graph_facts
            WHERE entity_id = ? AND key = 'email'
        """, (alice_id,)).fetchone()

        assert fact is not None
        assert fact['value'] == 'alice@example.com'
        conn.close()

    def test_graph_fact_multiword_value(self, sample_entities, monkeypatch, capsys):
        """Test adding fact with multi-word value."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'fact', 'Alice', 'role', 'Senior Software Engineer'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Set fact' in captured.out

        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        fact = conn.execute("""
            SELECT * FROM graph_facts WHERE entity_id = ? AND key = 'role'
        """, (alice_id,)).fetchone()
        assert fact['value'] == 'Senior Software Engineer'
        conn.close()

    def test_graph_facts_shown_in_get(self, sample_entities, monkeypatch, capsys):
        """Test facts appear in entity get."""
        # Add a fact
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        conn.execute("""
            INSERT INTO graph_facts (entity_id, key, value, confidence)
            VALUES (?, ?, ?, ?)
        """, (alice_id, 'location', 'San Francisco', 1.0))
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'get', 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Facts' in captured.out or 'location' in captured.out or 'San Francisco' in captured.out


class TestGraphSpreadCommand:
    """Test spreading activation."""

    def test_graph_spread(self, sample_graph_entities, monkeypatch, capsys):
        """Test spreading activation from an entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'spread', 'Kobus'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Spreading activation' in captured.out
        assert 'Kobus' in captured.out

    def test_graph_spread_with_depth(self, sample_graph_entities, monkeypatch, capsys):
        """Test spreading activation with custom depth."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'spread', 'Kobus', '3'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'depth=3' in captured.out

    def test_graph_spread_nonexistent(self, temp_db, monkeypatch, capsys):
        """Test spreading from non-existent entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'spread', 'NonExistent'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'No connected entities' in captured.out or "doesn't exist" in captured.out


class TestGraphMemoryLinking:
    """Test linking memories to entities."""

    def test_graph_link_memory(self, sample_memory, sample_entities, monkeypatch, capsys):
        """Test linking a memory to an entity."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'link', str(sample_memory), 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Linked memory' in captured.out
        assert str(sample_memory) in captured.out
        assert 'Alice' in captured.out

        # Verify in database
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        link = conn.execute("""
            SELECT * FROM memory_entity_links
            WHERE memory_id = ? AND entity_id = ?
        """, (sample_memory, alice_id)).fetchone()

        assert link is not None
        conn.close()

    def test_graph_auto_link(self, db_with_samples, sample_entities, monkeypatch, capsys):
        """Test auto-linking all memories."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'auto-link'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Auto-linked' in captured.out

    def test_graph_linked_memories_in_get(self, sample_memory, sample_entities, monkeypatch, capsys):
        """Test linked memories appear in entity get."""
        # Link a memory
        conn = database.get_db()
        alice_id = conn.execute("SELECT id FROM graph_entities WHERE name = 'Alice'").fetchone()['id']
        conn.execute("""
            INSERT INTO memory_entity_links (memory_id, entity_id)
            VALUES (?, ?)
        """, (sample_memory, alice_id))
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'get', 'Alice'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Linked memories' in captured.out or f'#{sample_memory}' in captured.out


class TestGraphImport:
    """Test graph import commands."""

    def test_graph_import_openclaw(self, temp_db, monkeypatch, capsys, tmp_path):
        """Test importing from OpenClaw."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'import-openclaw'
        ])

        # Mock the import function
        with patch('memory_tool.graph.graph_import_openclaw'):
            cli.main()

        # Should complete
        assert True


class TestGraphUnknownCommand:
    """Test unknown graph subcommands."""

    def test_graph_unknown_subcommand(self, temp_db, monkeypatch, capsys):
        """Test unknown graph subcommand shows help."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'graph', 'unknown'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert 'Unknown graph subcommand' in captured.out
        assert 'Graph commands:' in captured.out
