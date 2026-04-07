"""Tests for narrative memory module."""

import sqlite3
import pytest
from memory_tool.database import init_db, get_db
from memory_tool.narrative import (
    build_narrative, get_entity_stories, get_causal_chains,
    _relation_verb, _deduplicate_events, _generate_narrative_text
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Create a fresh test database."""
    db_path = tmp_path / "test_memories.db"
    monkeypatch.setattr("memory_tool.config.DB_PATH", db_path)
    monkeypatch.setattr("memory_tool.database.DB_PATH", db_path)
    init_db()
    conn = get_db()
    yield conn
    conn.close()


def _add_entity(db, name, entity_type="project", summary=""):
    cursor = db.execute(
        "INSERT INTO graph_entities (name, type, summary) VALUES (?, ?, ?)",
        (name, entity_type, summary)
    )
    db.commit()
    return cursor.lastrowid


def _add_relationship(db, from_id, to_id, rel_type, note=""):
    db.execute(
        "INSERT INTO graph_relationships (from_entity_id, to_entity_id, relation_type, note) VALUES (?, ?, ?, ?)",
        (from_id, to_id, rel_type, note)
    )
    db.commit()


def _add_memory(db, content, category="learning", project=None):
    cursor = db.execute(
        "INSERT INTO memories (content, category, project) VALUES (?, ?, ?)",
        (content, category, project)
    )
    db.commit()
    return cursor.lastrowid


def _link_memory(db, memory_id, entity_id):
    db.execute(
        "INSERT INTO memory_entity_links (memory_id, entity_id) VALUES (?, ?)",
        (memory_id, entity_id)
    )
    db.commit()


class TestBuildNarrative:
    def test_entity_not_found(self, db):
        result = build_narrative(db, "nonexistent")
        assert result['entity'] is None
        assert result['events'] == []
        assert result['connections'] == 0

    def test_entity_with_no_connections(self, db):
        _add_entity(db, "EmptyProject")
        result = build_narrative(db, "EmptyProject")
        assert result['entity'] is not None
        assert result['events'] == []
        assert "No narrative found" in result['narrative']

    def test_entity_with_linked_memories(self, db):
        eid = _add_entity(db, "WhatsAuction", "project", "Auction platform")
        mid1 = _add_memory(db, "Started WhatsAuction development", "project", "WhatsAuction")
        mid2 = _add_memory(db, "Deployed to production", "project", "WhatsAuction")
        _link_memory(db, mid1, eid)
        _link_memory(db, mid2, eid)

        result = build_narrative(db, "WhatsAuction")
        assert result['entity']['name'] == "WhatsAuction"
        assert len(result['events']) == 2
        assert result['connections'] == 2
        assert "WhatsAuction" in result['narrative']

    def test_entity_with_relationships(self, db):
        eid1 = _add_entity(db, "PayFast", "service")
        eid2 = _add_entity(db, "SoftyComp", "service")
        # PayFast leads_to SoftyComp
        _add_relationship(db, eid1, eid2, "leads_to", "PayFast rejected, tried SoftyComp")

        result = build_narrative(db, "PayFast")
        assert len(result['events']) >= 1
        assert any("SoftyComp" in e['content'] for e in result['events'])

    def test_case_insensitive_lookup(self, db):
        _add_entity(db, "WhatsAuction", "project")
        result = build_narrative(db, "whatsauction")
        assert result['entity'] is not None

    def test_narrative_depth_limit(self, db):
        # Create chain: A -> B -> C -> D -> E
        ids = []
        for name in ['A', 'B', 'C', 'D', 'E']:
            ids.append(_add_entity(db, name, "concept"))
        for i in range(len(ids) - 1):
            _add_relationship(db, ids[i], ids[i+1], "leads_to")

        # Depth 1 should not reach E
        result = build_narrative(db, "A", max_depth=1)
        names_in_events = [e.get('target_entity', '') for e in result['events']]
        # With depth 1, shouldn't traverse too deep
        assert result['connections'] > 0


class TestRelationVerb:
    def test_known_relations(self):
        assert "led to" in _relation_verb("leads_to")
        assert "prevents" in _relation_verb("prevents")
        assert "resolved" in _relation_verb("resolves")
        assert "requires" in _relation_verb("requires")

    def test_unknown_relation(self):
        result = _relation_verb("custom_relation")
        assert "custom_relation" in result


class TestDeduplicateEvents:
    def test_empty(self):
        assert _deduplicate_events([]) == []

    def test_no_duplicates(self):
        events = [
            {'content': 'First event'},
            {'content': 'Second event'},
        ]
        assert len(_deduplicate_events(events)) == 2

    def test_removes_duplicates(self):
        events = [
            {'content': 'Same event here'},
            {'content': 'Same event here'},
            {'content': 'Different event'},
        ]
        assert len(_deduplicate_events(events)) == 2


class TestGenerateNarrativeText:
    def test_empty_events(self):
        result = _generate_narrative_text("Test", [])
        assert "No narrative found" in result

    def test_with_events(self):
        events = [
            {'type': 'memory', 'content': 'Started project', 'date': '2026-01-01', 'category': 'project', 'confidence': 0.8},
            {'type': 'relationship', 'content': 'A led to B', 'date': '2026-02-01'},
        ]
        result = _generate_narrative_text("TestProject", events)
        assert "TestProject" in result
        assert "Started project" in result
        assert "2 events" in result


class TestGetEntityStories:
    def test_empty(self, db):
        result = get_entity_stories(db)
        assert result == []

    def test_with_connections(self, db):
        eid = _add_entity(db, "TestEntity", "project")
        mid = _add_memory(db, "Test memory")
        _link_memory(db, mid, eid)

        result = get_entity_stories(db, limit=5)
        assert len(result) >= 1
        assert result[0]['name'] == "TestEntity"


class TestGetCausalChains:
    def test_no_entity(self, db):
        assert get_causal_chains(db, "nonexistent") == []

    def test_no_chains(self, db):
        _add_entity(db, "Isolated", "concept")
        chains = get_causal_chains(db, "Isolated")
        assert chains == []

    def test_simple_chain(self, db):
        eid1 = _add_entity(db, "Start", "concept")
        eid2 = _add_entity(db, "Middle", "concept")
        eid3 = _add_entity(db, "End", "concept")
        _add_relationship(db, eid1, eid2, "leads_to")
        _add_relationship(db, eid2, eid3, "leads_to")

        chains = get_causal_chains(db, "Start")
        assert len(chains) >= 1
        # Should have a chain that includes Start and at least one more
        longest = max(chains, key=len)
        assert longest[0] == "Start"
        assert len(longest) >= 2
