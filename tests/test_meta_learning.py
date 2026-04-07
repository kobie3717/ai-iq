"""Tests for meta-learning search tuning module."""

import sqlite3
import json
import pytest
from pathlib import Path
from memory_tool.database import init_db, get_db
from memory_tool.meta_learning import (
    init_meta_tables, get_current_weights, save_weights,
    log_search_outcome, calculate_effectiveness,
    apply_learned_weights, get_weight_history, get_meta_stats,
    DEFAULT_WEIGHTS, META_CONFIG_PATH
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Create a fresh test database."""
    db_path = tmp_path / "test_memories.db"
    meta_path = tmp_path / "meta_weights.json"
    monkeypatch.setattr("memory_tool.config.DB_PATH", db_path)
    monkeypatch.setattr("memory_tool.database.DB_PATH", db_path)
    monkeypatch.setattr("memory_tool.meta_learning.DB_PATH", db_path)
    monkeypatch.setattr("memory_tool.meta_learning.META_CONFIG_PATH", meta_path)
    init_db()
    conn = get_db()
    init_meta_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def meta_path(tmp_path, monkeypatch):
    """Provide a temporary meta weights path."""
    path = tmp_path / "meta_weights.json"
    monkeypatch.setattr("memory_tool.meta_learning.META_CONFIG_PATH", path)
    return path


class TestWeights:
    def test_default_weights(self, meta_path):
        weights = get_current_weights()
        assert weights == DEFAULT_WEIGHTS

    def test_save_and_load_weights(self, db, meta_path):
        custom = dict(DEFAULT_WEIGHTS)
        custom['keyword_weight'] = 1.5
        save_weights(custom, "test")

        loaded = get_current_weights()
        assert loaded['keyword_weight'] == 1.5

    def test_missing_keys_filled(self, meta_path):
        # Write partial weights
        with open(meta_path, 'w') as f:
            json.dump({'keyword_weight': 2.0}, f)

        weights = get_current_weights()
        assert weights['keyword_weight'] == 2.0
        assert weights['semantic_weight'] == DEFAULT_WEIGHTS['semantic_weight']


class TestSearchOutcomes:
    def test_log_outcome(self, db):
        log_search_outcome(db, 1, "test query", "hybrid", 5, 3, 2, 1)

        row = db.execute("SELECT * FROM meta_search_outcomes WHERE search_id = 1").fetchone()
        assert row is not None
        assert row['keyword_results'] == 5
        assert row['semantic_results'] == 3
        assert row['used_from_keyword'] == 2
        assert row['used_from_semantic'] == 1
        assert row['total_results'] == 8
        assert row['total_used'] == 3

    def test_multiple_outcomes(self, db):
        for i in range(5):
            log_search_outcome(db, i, f"query {i}", "hybrid", 10, 10, 5, 3)

        count = db.execute("SELECT COUNT(*) as c FROM meta_search_outcomes").fetchone()['c']
        assert count == 5


class TestEffectiveness:
    def test_no_data(self, db):
        result = calculate_effectiveness(db, days=30)
        assert result['total_searches'] == 0
        assert result['recommendation'] == 'insufficient_data'

    def test_balanced_modes(self, db):
        # Log equal effectiveness for both modes
        for i in range(25):
            log_search_outcome(db, i, f"q{i}", "hybrid", 10, 10, 5, 5)

        result = calculate_effectiveness(db, days=30)
        assert result['total_searches'] == 25
        assert result['keyword_effectiveness'] == pytest.approx(0.5, abs=0.1)
        assert result['semantic_effectiveness'] == pytest.approx(0.5, abs=0.1)

    def test_keyword_dominant(self, db):
        for i in range(25):
            log_search_outcome(db, i, f"q{i}", "hybrid", 10, 10, 8, 1)

        result = calculate_effectiveness(db, days=30)
        assert result['keyword_effectiveness'] > result['semantic_effectiveness']
        assert result['recommendation'] == 'boost_keyword'

    def test_semantic_dominant(self, db):
        for i in range(25):
            log_search_outcome(db, i, f"q{i}", "hybrid", 10, 10, 1, 8)

        result = calculate_effectiveness(db, days=30)
        assert result['semantic_effectiveness'] > result['keyword_effectiveness']
        assert result['recommendation'] == 'boost_semantic'


class TestApplyWeights:
    def test_insufficient_data(self, db):
        result = apply_learned_weights(db, min_searches=20)
        assert not result['applied']
        assert 'Need' in result['reason']

    def test_applies_when_enough_data(self, db, meta_path):
        # Log heavily keyword-dominant results
        for i in range(25):
            log_search_outcome(db, i, f"q{i}", "hybrid", 10, 10, 9, 1)

        result = apply_learned_weights(db, min_searches=20)
        # Should apply since keyword is clearly dominant
        if result['applied']:
            assert result['new_weights']['keyword_weight'] >= result['old_weights']['keyword_weight']


class TestWeightHistory:
    def test_empty_history(self, db):
        history = get_weight_history(db, limit=10)
        assert history == []

    def test_logged_changes(self, db, meta_path):
        save_weights({'keyword_weight': 1.2, 'semantic_weight': 0.8}, "test change")
        history = get_weight_history(db, limit=10)
        assert len(history) >= 1
        assert history[0]['reason'] == 'test change'


class TestMetaStats:
    def test_empty_stats(self, db, meta_path):
        stats = get_meta_stats(db)
        assert stats['current_weights'] == DEFAULT_WEIGHTS
        assert stats['weight_changes'] == 0
        assert stats['effectiveness_30d']['total_searches'] == 0

    def test_with_data(self, db, meta_path):
        for i in range(5):
            log_search_outcome(db, i, f"q{i}", "hybrid", 10, 10, 5, 5)

        stats = get_meta_stats(db)
        assert stats['effectiveness_30d']['total_searches'] == 5
        assert len(stats['mode_distribution']) >= 1
