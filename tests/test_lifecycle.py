"""Tests for truth lifecycle states (Feature 1)."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import database, beliefs_extended


def test_set_and_get_belief_state(temp_db):
    """Test setting and getting belief lifecycle states."""
    conn = database.get_db()

    # Create a belief
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence, category)
        VALUES (?, ?, ?)
    """, ("Test belief", 0.7, "general"))
    belief_id = cursor.lastrowid
    conn.commit()

    # Check default state
    state = beliefs_extended.get_belief_state(conn, belief_id)
    assert state == 'hypothesis'

    # Transition to tested
    beliefs_extended.set_belief_state(conn, belief_id, 'tested', "Manual test")
    state = beliefs_extended.get_belief_state(conn, belief_id)
    assert state == 'tested'

    # Transition to validated
    beliefs_extended.set_belief_state(conn, belief_id, 'validated')
    state = beliefs_extended.get_belief_state(conn, belief_id)
    assert state == 'validated'

    # Verify revision was logged
    revisions = conn.execute("""
        SELECT * FROM belief_revisions WHERE belief_id = ? AND revision_type = 'lifecycle'
    """, (belief_id,)).fetchall()
    assert len(revisions) == 2  # tested + validated

    conn.close()


def test_invalid_state_transition(temp_db):
    """Test that invalid states are rejected."""
    conn = database.get_db()

    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence)
        VALUES (?, ?)
    """, ("Test belief", 0.5))
    belief_id = cursor.lastrowid
    conn.commit()

    # Try to set invalid state
    with pytest.raises(ValueError):
        beliefs_extended.set_belief_state(conn, belief_id, 'invalid_state')

    conn.close()


def test_list_beliefs_by_state(temp_db):
    """Test filtering beliefs by lifecycle state."""
    conn = database.get_db()

    # Create beliefs in different states
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence, belief_state)
        VALUES (?, ?, ?)
    """, ("Hypothesis belief", 0.5, "hypothesis"))
    hyp_id = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence, belief_state)
        VALUES (?, ?, ?)
    """, ("Validated belief", 0.9, "validated"))
    val_id = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence, belief_state)
        VALUES (?, ?, ?)
    """, ("Deprecated belief", 0.1, "deprecated"))
    dep_id = cursor.lastrowid

    conn.commit()

    # List hypotheses
    hypotheses = beliefs_extended.list_beliefs_by_state(conn, 'hypothesis')
    assert len(hypotheses) == 1
    assert hypotheses[0]['id'] == hyp_id

    # List validated
    validated = beliefs_extended.list_beliefs_by_state(conn, 'validated')
    assert len(validated) == 1
    assert validated[0]['id'] == val_id

    # List deprecated
    deprecated = beliefs_extended.list_beliefs_by_state(conn, 'deprecated')
    assert len(deprecated) == 1
    assert deprecated[0]['id'] == dep_id

    conn.close()


def test_auto_transition_on_prediction_confirmed(temp_db):
    """Test auto-transition when prediction is confirmed."""
    conn = database.get_db()

    # Create a memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content)
        VALUES (?, ?)
    """, ("learning", "Test memory"))
    mem_id = cursor.lastrowid

    # Create a belief linked to this memory
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state)
        VALUES (?, ?, ?, ?)
    """, (mem_id, "This will work", 0.7, "tested"))
    belief_id = cursor.lastrowid

    # Create a prediction
    cursor = conn.execute("""
        INSERT INTO predictions (memory_id, prediction, confidence)
        VALUES (?, ?, ?)
    """, (mem_id, "It will succeed", 0.7))
    pred_id = cursor.lastrowid

    conn.commit()

    # Auto-transition on confirmation
    transitioned = beliefs_extended.auto_transition_on_prediction(conn, pred_id, confirmed=True)

    assert len(transitioned) == 1
    assert transitioned[0] == belief_id

    # Check state was updated to validated
    state = beliefs_extended.get_belief_state(conn, belief_id)
    assert state == 'validated'

    conn.close()


def test_auto_transition_on_prediction_refuted(temp_db):
    """Test auto-transition when prediction is refuted."""
    conn = database.get_db()

    # Create a memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content)
        VALUES (?, ?)
    """, ("learning", "Test memory"))
    mem_id = cursor.lastrowid

    # Create a belief linked to this memory
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state)
        VALUES (?, ?, ?, ?)
    """, (mem_id, "This will work", 0.7, "tested"))
    belief_id = cursor.lastrowid

    # Create a prediction
    cursor = conn.execute("""
        INSERT INTO predictions (memory_id, prediction, confidence)
        VALUES (?, ?, ?)
    """, (mem_id, "It will succeed", 0.7))
    pred_id = cursor.lastrowid

    conn.commit()

    # Auto-transition on refutation
    transitioned = beliefs_extended.auto_transition_on_prediction(conn, pred_id, confirmed=False)

    assert len(transitioned) == 1
    assert transitioned[0] == belief_id

    # Check state was updated to refuted
    state = beliefs_extended.get_belief_state(conn, belief_id)
    assert state == 'refuted'

    conn.close()


def test_auto_deprecate_weak_beliefs(temp_db):
    """Test auto-deprecation of weak, stale beliefs."""
    conn = database.get_db()

    # Create a memory (not accessed recently)
    cursor = conn.execute("""
        INSERT INTO memories (category, content, access_count)
        VALUES (?, ?, ?)
    """, ("learning", "Old memory", 2))
    mem_id = cursor.lastrowid

    # Create a weak belief (confidence < 0.2, old, not validated)
    old_date = (datetime.now() - timedelta(days=70)).strftime('%Y-%m-%d')
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (mem_id, "Weak old belief", 0.15, "hypothesis", old_date))
    weak_belief_id = cursor.lastrowid

    # Create a strong belief (should not be deprecated)
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (mem_id, "Strong old belief", 0.8, "hypothesis", old_date))
    strong_belief_id = cursor.lastrowid

    # Create a recent weak belief (should not be deprecated)
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state)
        VALUES (?, ?, ?, ?)
    """, (mem_id, "Recent weak belief", 0.1, "hypothesis"))
    recent_belief_id = cursor.lastrowid

    conn.commit()

    # Run auto-deprecation
    deprecated_count = beliefs_extended.auto_deprecate_weak_beliefs(conn, days_inactive=60)

    assert deprecated_count == 1

    # Check that weak old belief was deprecated
    weak_state = beliefs_extended.get_belief_state(conn, weak_belief_id)
    assert weak_state == 'deprecated'

    # Check that strong belief was not deprecated
    strong_state = beliefs_extended.get_belief_state(conn, strong_belief_id)
    assert strong_state == 'hypothesis'

    # Check that recent belief was not deprecated
    recent_state = beliefs_extended.get_belief_state(conn, recent_belief_id)
    assert recent_state == 'hypothesis'

    conn.close()


def test_auto_deprecate_respects_access_immunity(temp_db):
    """Test that beliefs with high access count are immune to deprecation."""
    conn = database.get_db()

    # Create a memory with high access count (immune)
    cursor = conn.execute("""
        INSERT INTO memories (category, content, access_count)
        VALUES (?, ?, ?)
    """, ("learning", "Popular memory", 10))
    immune_mem_id = cursor.lastrowid

    # Create a weak, old belief linked to high-access memory
    old_date = (datetime.now() - timedelta(days=70)).strftime('%Y-%m-%d')
    cursor = conn.execute("""
        INSERT INTO beliefs (memory_id, statement, confidence, belief_state, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (immune_mem_id, "Weak but popular belief", 0.1, "hypothesis", old_date))
    immune_belief_id = cursor.lastrowid

    conn.commit()

    # Run auto-deprecation
    deprecated_count = beliefs_extended.auto_deprecate_weak_beliefs(conn, days_inactive=60)

    assert deprecated_count == 0

    # Check that belief was NOT deprecated (protected by access count)
    state = beliefs_extended.get_belief_state(conn, immune_belief_id)
    assert state == 'hypothesis'

    conn.close()
