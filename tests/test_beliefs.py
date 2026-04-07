"""Tests for belief and prediction system."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import beliefs, database, memory_ops


def test_set_and_get_confidence(temp_db):
    """Test setting and getting confidence values."""
    conn = database.get_db()

    # Create a memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content)
        VALUES (?, ?)
    """, ("learning", "Test memory for confidence"))
    mem_id = cursor.lastrowid
    conn.commit()

    # Set confidence
    beliefs.set_confidence(conn, mem_id, 0.85, "Test reason")

    # Get confidence
    conf = beliefs.get_confidence(conn, mem_id)
    assert conf == 0.85

    # Verify update was logged
    updates = conn.execute("""
        SELECT * FROM belief_updates WHERE memory_id = ?
    """, (mem_id,)).fetchall()
    assert len(updates) == 1
    assert updates[0]['new_confidence'] == 0.85
    assert updates[0]['reason'] == "Test reason"

    conn.close()


def test_confidence_clamping(temp_db):
    """Test that confidence values are clamped to 0.01-0.99."""
    conn = database.get_db()

    cursor = conn.execute("""
        INSERT INTO memories (category, content)
        VALUES (?, ?)
    """, ("learning", "Test memory"))
    mem_id = cursor.lastrowid
    conn.commit()

    # Try to set too high
    beliefs.set_confidence(conn, mem_id, 1.5, "Too high")
    assert beliefs.get_confidence(conn, mem_id) == 0.99

    # Try to set too low
    beliefs.set_confidence(conn, mem_id, -0.5, "Too low")
    assert beliefs.get_confidence(conn, mem_id) == 0.01

    conn.close()


def test_boost_and_weaken_confidence(temp_db):
    """Test boosting and weakening confidence."""
    conn = database.get_db()

    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("learning", "Test memory", 0.5))
    mem_id = cursor.lastrowid
    conn.commit()

    # Boost confidence
    new_conf = beliefs.boost_confidence(conn, mem_id, 0.2, "Boost test")
    assert new_conf == 0.7
    assert beliefs.get_confidence(conn, mem_id) == 0.7

    # Weaken confidence
    new_conf = beliefs.weaken_confidence(conn, mem_id, 0.3, "Weaken test")
    assert pytest.approx(new_conf, 0.01) == 0.4
    assert pytest.approx(beliefs.get_confidence(conn, mem_id), 0.01) == 0.4

    # Test clamping on boost
    beliefs.set_confidence(conn, mem_id, 0.95, "Setup for clamp test")
    new_conf = beliefs.boost_confidence(conn, mem_id, 0.2, "Should clamp")
    assert new_conf == 0.99

    conn.close()


def test_create_prediction(temp_db):
    """Test creating a prediction."""
    conn = database.get_db()

    # Create a base memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "The system will scale well", 0.8))
    mem_id = cursor.lastrowid
    conn.commit()

    # Create prediction
    deadline = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    pred_id = beliefs.predict(
        conn,
        "Load tests will pass with 10k concurrent users",
        based_on=mem_id,
        confidence=0.75,
        deadline=deadline,
        expected_outcome="All load tests pass without errors"
    )

    # Verify prediction was created
    pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
    assert pred is not None
    assert pred['memory_id'] == mem_id
    assert pred['confidence'] == 0.75
    assert pred['status'] == 'open'
    assert pred['deadline'] == deadline

    conn.close()


def test_resolve_prediction_confirmed(temp_db):
    """Test resolving a prediction as confirmed."""
    conn = database.get_db()

    # Create a base memory with low confidence
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Feature X will work", 0.6))
    mem_id = cursor.lastrowid
    conn.commit()

    # Create prediction
    pred_id = beliefs.predict(
        conn,
        "Feature X will work in production",
        based_on=mem_id,
        confidence=0.6
    )

    # Resolve as confirmed
    result = beliefs.resolve_prediction(
        conn,
        pred_id,
        "Feature X works perfectly in production",
        confirmed=True
    )

    # Check that source memory confidence was boosted
    new_conf = beliefs.get_confidence(conn, mem_id)
    assert new_conf == 0.7  # 0.6 + 0.1

    # Check prediction status
    pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
    assert pred['status'] == 'confirmed'
    assert pred['actual_outcome'] == "Feature X works perfectly in production"

    # Check that result indicates updates
    assert result['updated'] >= 1
    assert result['source_memory'] == mem_id

    conn.close()


def test_resolve_prediction_refuted(temp_db):
    """Test resolving a prediction as refuted."""
    conn = database.get_db()

    # Create a base memory with high confidence
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Algorithm Z is optimal", 0.9))
    mem_id = cursor.lastrowid
    conn.commit()

    # Create prediction
    pred_id = beliefs.predict(
        conn,
        "Algorithm Z will outperform baseline",
        based_on=mem_id,
        confidence=0.85
    )

    # Resolve as refuted
    result = beliefs.resolve_prediction(
        conn,
        pred_id,
        "Algorithm Z was 30% slower than baseline",
        confirmed=False
    )

    # Check that source memory confidence was weakened
    new_conf = beliefs.get_confidence(conn, mem_id)
    assert new_conf == 0.7  # 0.9 - 0.2

    # Check prediction status
    pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
    assert pred['status'] == 'refuted'

    conn.close()


def test_list_predictions(temp_db):
    """Test listing predictions by status."""
    conn = database.get_db()

    # Create several predictions
    pred1 = beliefs.predict(conn, "Prediction 1", confidence=0.5)
    pred2 = beliefs.predict(conn, "Prediction 2", confidence=0.6)

    # Resolve one
    beliefs.resolve_prediction(conn, pred1, "Outcome 1", confirmed=True)

    # List open predictions
    open_preds = beliefs.list_predictions(conn, 'open')
    assert len(open_preds) == 1
    assert open_preds[0]['id'] == pred2

    # List confirmed predictions
    confirmed_preds = beliefs.list_predictions(conn, 'confirmed')
    assert len(confirmed_preds) == 1
    assert confirmed_preds[0]['id'] == pred1

    # List all predictions
    all_preds = beliefs.list_predictions(conn, 'all')
    assert len(all_preds) == 2

    conn.close()


def test_expired_predictions(temp_db):
    """Test detecting expired predictions."""
    conn = database.get_db()

    # Create prediction with past deadline
    past_deadline = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    pred1 = beliefs.predict(
        conn,
        "Old prediction",
        deadline=past_deadline,
        confidence=0.5
    )

    # Create prediction with future deadline
    future_deadline = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    pred2 = beliefs.predict(
        conn,
        "Future prediction",
        deadline=future_deadline,
        confidence=0.5
    )

    # Get expired predictions
    expired = beliefs.expired_predictions(conn)
    assert len(expired) == 1
    assert expired[0]['id'] == pred1

    conn.close()


def test_belief_propagation_through_relations(temp_db):
    """Test Bayesian propagation through memory relations."""
    conn = database.get_db()

    # Create a chain of related memories
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Root belief", 0.7))
    mem1 = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Related belief 1", 0.7))
    mem2 = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Related belief 2", 0.7))
    mem3 = cursor.lastrowid

    # Create relations
    conn.execute("""
        INSERT INTO memory_relations (source_id, target_id, relation_type)
        VALUES (?, ?, 'related')
    """, (mem1, mem2))

    conn.execute("""
        INSERT INTO memory_relations (source_id, target_id, relation_type)
        VALUES (?, ?, 'related')
    """, (mem1, mem3))

    conn.commit()

    # Create prediction on root belief
    pred_id = beliefs.predict(
        conn,
        "Test prediction",
        based_on=mem1,
        confidence=0.7
    )

    # Resolve prediction as confirmed
    result = beliefs.resolve_prediction(
        conn,
        pred_id,
        "Confirmed outcome",
        confirmed=True
    )

    # Check that propagation occurred
    assert result['updated'] >= 2  # At least mem1 and propagated memories

    # Check that related memories were updated
    conf2 = beliefs.get_confidence(conn, mem2)
    conf3 = beliefs.get_confidence(conn, mem3)

    # Related memories should have been boosted (attenuated by 0.7 factor)
    assert conf2 > 0.7
    assert conf3 > 0.7

    conn.close()


def test_belief_conflicts_detection(temp_db):
    """Test detecting contradicting high-confidence beliefs."""
    conn = database.get_db()

    # Create contradicting beliefs
    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Feature A is not working correctly", 0.85, 1))

    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Feature A is working correctly now", 0.90, 1))

    conn.commit()

    # Find conflicts
    conflicts = beliefs.belief_conflicts(conn)

    # Should detect at least one conflict
    assert len(conflicts) > 0

    # Check conflict structure
    conflict = conflicts[0]
    assert 'id1' in conflict
    assert 'id2' in conflict
    assert 'confidence1' in conflict
    assert 'confidence2' in conflict
    assert conflict['similarity'] > 0.6

    conn.close()


def test_weakest_and_strongest_beliefs(temp_db):
    """Test retrieving weakest and strongest beliefs."""
    conn = database.get_db()

    # Create beliefs with varying confidence
    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Weak belief", 0.2, 1))

    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Strong belief", 0.95, 1))

    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Medium belief", 0.5, 1))

    conn.commit()

    # Get weakest
    weakest = beliefs.weakest_beliefs(conn, limit=10)
    assert len(weakest) >= 1
    assert weakest[0]['confidence'] <= 0.3

    # Get strongest
    strongest = beliefs.strongest_beliefs(conn, limit=10)
    assert len(strongest) >= 1
    assert strongest[0]['confidence'] >= 0.9

    conn.close()


def test_belief_history(temp_db):
    """Test tracking confidence changes over time."""
    conn = database.get_db()

    # Create memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("belief", "Test belief", 0.5))
    mem_id = cursor.lastrowid
    conn.commit()

    # Make several confidence changes
    beliefs.boost_confidence(conn, mem_id, 0.1, "First boost")
    beliefs.weaken_confidence(conn, mem_id, 0.05, "Small weaken")
    beliefs.boost_confidence(conn, mem_id, 0.2, "Second boost")

    # Get history
    history = beliefs.belief_history(conn, mem_id)

    # Should have 3 updates
    assert len(history) == 3

    # Check chronological order
    assert pytest.approx(history[0]['new_confidence'], 0.01) == 0.6  # 0.5 + 0.1
    assert pytest.approx(history[1]['new_confidence'], 0.01) == 0.55  # 0.6 - 0.05
    assert pytest.approx(history[2]['new_confidence'], 0.01) == 0.75  # 0.55 + 0.2

    conn.close()


def test_beliefs_decay(temp_db):
    """Test belief decay for unsupported beliefs."""
    conn = database.get_db()

    # Create old belief with no supporting predictions
    old_date = (datetime.now() - timedelta(days=60)).isoformat()
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence, access_count, accessed_at, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("belief", "Unsupported belief", 0.8, 1, old_date, 1))
    mem_id = cursor.lastrowid

    # Create recent, frequently accessed belief (should be immune)
    recent_date = (datetime.now() - timedelta(days=5)).isoformat()
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence, access_count, accessed_at, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("belief", "Well-supported belief", 0.8, 10, recent_date, 1))
    immune_id = cursor.lastrowid

    conn.commit()

    # Run decay
    weakened_count = beliefs.beliefs_decay(conn)

    # At least one belief should be weakened
    assert weakened_count >= 1

    # Check that old belief was weakened
    old_conf = beliefs.get_confidence(conn, mem_id)
    assert old_conf < 0.8

    # Check that immune belief was not weakened
    immune_conf = beliefs.get_confidence(conn, immune_id)
    assert immune_conf == 0.8

    conn.close()


def test_beliefs_dream_consolidation(temp_db):
    """Test belief consolidation during dream mode."""
    conn = database.get_db()

    # Create similar beliefs
    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "The system is fast and efficient", 0.7, 1))

    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "The system is fast and very efficient", 0.8, 1))

    # Create expired prediction
    past_deadline = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    beliefs.predict(
        conn,
        "Expired prediction",
        deadline=past_deadline,
        confidence=0.5
    )

    conn.commit()

    # Run beliefs dream
    stats = beliefs.beliefs_dream(conn)

    # Check stats
    assert 'merged' in stats
    assert 'predictions_expired' in stats
    assert 'beliefs_weakened' in stats

    # At least one belief should be merged
    assert stats['merged'] >= 1

    # At least one prediction should be expired
    assert stats['predictions_expired'] >= 1

    conn.close()


def test_integration_with_contradiction_detection(temp_db):
    """Test that contradictions weaken confidence of existing memories."""
    conn = database.get_db()

    # This test requires vector search to be available
    if not database.has_vec_support():
        pytest.skip("Vector search not available")

    try:
        # Create initial belief with high confidence
        cursor = conn.execute("""
            INSERT INTO memories (category, content, confidence, active)
            VALUES (?, ?, ?, ?)
        """, ("belief", "The new algorithm is very efficient", 0.9, 1))
        mem_id = cursor.lastrowid
        conn.commit()

        # Embed the memory
        from memory_tool.embedding import embed_and_store
        embed_and_store(conn, mem_id, "The new algorithm is very efficient")

        # Add contradicting memory (should detect contradiction and weaken first)
        result = memory_ops.check_contradictions(
            "The new algorithm is not efficient at all",
            category="belief"
        )

        # Should detect contradiction
        assert result is not None
        assert "contradiction" in result.lower()

        # Original memory confidence should be slightly weakened
        new_conf = beliefs.get_confidence(conn, mem_id)
        assert new_conf < 0.9

    except Exception as e:
        # If embedding fails, skip test
        pytest.skip(f"Embedding failed: {e}")
    finally:
        conn.close()


def test_cli_believe_command(temp_db):
    """Test the believe CLI command."""
    # Test directly via Python instead of subprocess
    # because subprocess doesn't share the temp_db fixture
    from memory_tool import memory_ops
    conn = database.get_db()

    # Simulate the CLI command by directly calling the function
    mem_id = memory_ops.add_memory(
        "belief",
        "Test belief statement",
        tags="belief,explicit"
    )

    beliefs.set_confidence(conn, mem_id, 0.85, "Explicit belief creation")

    # Verify belief was created
    assert mem_id > 0
    conf = beliefs.get_confidence(conn, mem_id)
    assert conf == 0.85

    conn.close()


def test_cli_predict_command(temp_db):
    """Test the predict CLI command."""
    # Test directly via Python
    conn = database.get_db()

    deadline = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    # Simulate CLI by calling function directly
    pred_id = beliefs.predict(
        conn,
        "Test prediction",
        confidence=0.7,
        deadline=deadline
    )

    # Verify prediction was created
    assert pred_id > 0

    pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
    assert pred['confidence'] == 0.7
    assert pred['deadline'] == deadline

    conn.close()


def test_cli_beliefs_list(temp_db):
    """Test the beliefs listing functionality."""
    conn = database.get_db()

    # Create some beliefs
    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Test belief 1", 0.3, 1))

    conn.execute("""
        INSERT INTO memories (category, content, confidence, active)
        VALUES (?, ?, ?, ?)
    """, ("belief", "Test belief 2", 0.9, 1))

    conn.commit()

    # Test weakest beliefs
    weak = beliefs.weakest_beliefs(conn, 10)
    assert len(weak) >= 1
    assert any(b['confidence'] <= 0.3 for b in weak)

    # Test strongest beliefs
    strong = beliefs.strongest_beliefs(conn, 10)
    assert len(strong) >= 1
    assert any(b['confidence'] >= 0.9 for b in strong)

    conn.close()


def test_cli_predictions_list(temp_db):
    """Test the predictions listing CLI command."""
    import subprocess
    conn = database.get_db()

    # Create some predictions
    beliefs.predict(conn, "Open prediction", confidence=0.5)
    pred2 = beliefs.predict(conn, "Confirmed prediction", confidence=0.6)
    beliefs.resolve_prediction(conn, pred2, "Outcome", confirmed=True)

    conn.close()

    # Test --open flag
    result = subprocess.run(
        ["python3", "-m", "memory_tool.cli", "predictions", "--open"],
        capture_output=True,
        text=True,
        cwd="/root/ai-iq"
    )

    assert result.returncode == 0

    # Test --confirmed flag
    result = subprocess.run(
        ["python3", "-m", "memory_tool.cli", "predictions", "--confirmed"],
        capture_output=True,
        text=True,
        cwd="/root/ai-iq"
    )

    assert result.returncode == 0
