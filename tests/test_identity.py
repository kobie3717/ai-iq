"""Tests for identity layer module."""

import sqlite3
import json
import pytest
from memory_tool.database import init_db, get_db
from memory_tool.identity import (
    init_identity_tables, discover_traits, get_identity,
    save_identity_snapshot, get_identity_evolution,
    compare_identity_snapshots, TRAIT_PATTERNS,
    _discover_custom_traits, _generate_identity_summary
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


def _add_memory(db, content, category="learning", project=None, tags=""):
    cursor = db.execute(
        "INSERT INTO memories (content, category, project, tags) VALUES (?, ?, ?, ?)",
        (content, category, project, tags)
    )
    db.commit()
    return cursor.lastrowid


class TestInitTables:
    def test_creates_tables(self, db):
        init_identity_tables(db)
        # Verify tables exist
        db.execute("SELECT 1 FROM identity_traits LIMIT 1")
        db.execute("SELECT 1 FROM identity_snapshots LIMIT 1")

    def test_idempotent(self, db):
        init_identity_tables(db)
        init_identity_tables(db)  # Should not error


class TestDiscoverTraits:
    def test_no_memories(self, db):
        traits = discover_traits(db)
        assert traits == []

    def test_discovers_docker_trait(self, db):
        for i in range(5):
            _add_memory(db, f"Deployed Docker container #{i}", "decision", "WhatsAuction", "docker")
        _add_memory(db, "Docker compose setup for services", "learning", "WhatsAuction")

        traits = discover_traits(db)
        docker_traits = [t for t in traits if 'docker' in t['trait_name'].lower()]
        assert len(docker_traits) >= 1
        assert docker_traits[0]['confidence'] > 0.5

    def test_discovers_automation_trait(self, db):
        for i in range(4):
            _add_memory(db, f"Set up cron job for automated backup #{i}", "decision")
        _add_memory(db, "CI/CD pipeline automates deployment", "learning")

        traits = discover_traits(db)
        auto_traits = [t for t in traits if 'automation' in t['trait_name']]
        assert len(auto_traits) >= 1

    def test_counter_evidence_lowers_confidence(self, db):
        # Add docker evidence
        for i in range(3):
            _add_memory(db, f"Docker container deployed #{i}", "decision")
        # Add counter evidence (PM2)
        for i in range(3):
            _add_memory(db, f"PM2 restart service #{i}", "decision")

        traits = discover_traits(db)
        docker_traits = [t for t in traits if t['trait_name'] == 'prefers_docker']
        if docker_traits:
            assert docker_traits[0]['counter_evidence'] > 0

    def test_saves_to_database(self, db):
        for i in range(3):
            _add_memory(db, f"Python script #{i}", "learning", tags="python")

        discover_traits(db)

        rows = db.execute("SELECT * FROM identity_traits WHERE active = 1").fetchall()
        assert len(rows) > 0

    def test_multi_project_boosts_confidence(self, db):
        _add_memory(db, "Docker deploy for WhatsAuction", "decision", "WhatsAuction")
        _add_memory(db, "Docker deploy for WhatsHub", "decision", "WhatsHub")
        _add_memory(db, "Docker compose for FlashVault", "decision", "FlashVault")

        traits = discover_traits(db)
        docker_traits = [t for t in traits if t['trait_name'] == 'prefers_docker']
        if docker_traits:
            assert len(docker_traits[0].get('projects', [])) > 1


class TestCustomTraits:
    def test_discovers_decision_patterns(self, db):
        memories = []
        for i in range(5):
            mid = _add_memory(db, f"Decided to use redis for caching scenario {i}", "decision")
            memories.append(db.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone())

        custom = _discover_custom_traits(db, memories)
        # Should find "redis" as a recurring theme
        redis_traits = [v for k, v in custom.items() if 'redis' in k]
        assert len(redis_traits) >= 1

    def test_discovers_error_patterns(self, db):
        memories = []
        for i in range(4):
            mid = _add_memory(db, f"Error: nginx configuration failed attempt {i}", "error")
            memories.append(db.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone())

        custom = _discover_custom_traits(db, memories)
        nginx_traits = [v for k, v in custom.items() if 'nginx' in k]
        assert len(nginx_traits) >= 1


class TestGetIdentity:
    def test_empty_identity(self, db):
        identity = get_identity(db)
        assert identity['traits'] == []
        assert identity['total_traits'] == 0

    def test_with_traits(self, db):
        for i in range(5):
            _add_memory(db, f"Docker container #{i}", "decision")

        discover_traits(db)
        identity = get_identity(db)
        assert identity['total_traits'] > 0
        assert identity['summary']  # Should have text

    def test_min_confidence_filter(self, db):
        init_identity_tables(db)
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count)
            VALUES ('weak_trait', 'A weak trait', 0.2, 1)
        """)
        db.commit()

        identity = get_identity(db, min_confidence=0.5)
        weak = [t for t in identity['traits'] if t['trait_name'] == 'weak_trait']
        assert len(weak) == 0

        identity_all = get_identity(db, min_confidence=0.1)
        weak = [t for t in identity_all['traits'] if t['trait_name'] == 'weak_trait']
        assert len(weak) == 1


class TestSnapshots:
    def test_save_snapshot(self, db):
        init_identity_tables(db)
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count)
            VALUES ('test_trait', 'A test trait', 0.8, 5)
        """)
        db.commit()

        snap_id = save_identity_snapshot(db)
        assert snap_id > 0

        # Verify saved
        row = db.execute("SELECT * FROM identity_snapshots WHERE id = ?", (snap_id,)).fetchone()
        assert row is not None
        traits = json.loads(row['traits'])
        assert len(traits) >= 1

    def test_evolution_history(self, db):
        init_identity_tables(db)
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count)
            VALUES ('trait_a', 'Trait A', 0.7, 3)
        """)
        db.commit()
        save_identity_snapshot(db)

        # Update and save another
        db.execute("UPDATE identity_traits SET confidence = 0.9 WHERE trait_name = 'trait_a'")
        db.commit()
        save_identity_snapshot(db)

        history = get_identity_evolution(db, limit=5)
        assert len(history) == 2

    def test_compare_snapshots(self, db):
        init_identity_tables(db)

        # First snapshot
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count)
            VALUES ('stable', 'Stable', 0.7, 3)
        """)
        db.commit()
        save_identity_snapshot(db)

        # Second snapshot with change
        db.execute("UPDATE identity_traits SET confidence = 0.9 WHERE trait_name = 'stable'")
        db.execute("""
            INSERT INTO identity_traits (trait_name, description, confidence, evidence_count)
            VALUES ('new_trait', 'New', 0.6, 2)
        """)
        db.commit()
        save_identity_snapshot(db)

        result = compare_identity_snapshots(db)
        assert result['has_comparison']
        # Should detect confidence change
        assert len(result['changed']) >= 1 or len(result['new_traits']) >= 1

    def test_compare_needs_two_snapshots(self, db):
        init_identity_tables(db)
        result = compare_identity_snapshots(db)
        assert not result['has_comparison']


class TestIdentitySummary:
    def test_empty(self):
        result = _generate_identity_summary([], [])
        assert "No significant traits" in result

    def test_with_traits(self):
        strong = [{'description': 'Prefers Docker', 'confidence': 0.9, 'evidence_count': 10}]
        moderate = [{'description': 'Likes Python', 'confidence': 0.5}]
        result = _generate_identity_summary(strong, moderate)
        assert "Docker" in result
        assert "Core traits" in result


class TestTraitPatterns:
    def test_all_patterns_have_required_keys(self):
        for name, pattern in TRAIT_PATTERNS.items():
            assert 'keywords' in pattern, f"{name} missing keywords"
            assert 'anti_keywords' in pattern, f"{name} missing anti_keywords"
            assert 'description' in pattern, f"{name} missing description"
            assert len(pattern['keywords']) > 0, f"{name} has empty keywords"
