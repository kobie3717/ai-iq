"""Tests for extended belief and prediction system with evidence tracking."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import beliefs as beliefs_extended, database, memory_ops


def test_add_belief(temp_db):
    """Test adding a basic belief."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(
        conn,
        "The system scales well horizontally",
        confidence=0.7,
        category="architecture",
        source="observation"
    )

    assert belief_id > 0

    # Verify belief was created
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief is not None
    assert belief['statement'] == "The system scales well horizontally"
    assert belief['confidence'] == 0.7
    assert belief['category'] == "architecture"
    assert belief['status'] == 'active'

    conn.close()


def test_get_belief_with_evidence_stats(temp_db):
    """Test that get_belief returns evidence statistics."""
    conn = database.get_db()

    # Create belief
    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Add some evidence
    mem1 = memory_ops.add_memory("learning", "Supporting evidence", skip_dedup=True)
    mem2 = memory_ops.add_memory("learning", "Contradicting evidence", skip_dedup=True)

    beliefs_extended.add_evidence(conn, belief_id, mem1, "supports", 0.8)
    beliefs_extended.add_evidence(conn, belief_id, mem2, "contradicts", 0.6)

    # Get belief with stats
    belief = beliefs_extended.get_belief(conn, belief_id)

    assert belief['supports_count'] == 1
    assert belief['contradicts_count'] == 1
    assert pytest.approx(belief['avg_support_strength'], 0.01) == 0.8
    assert pytest.approx(belief['avg_contradict_strength'], 0.01) == 0.6

    conn.close()


def test_list_beliefs_filtering(temp_db):
    """Test listing beliefs with filters."""
    conn = database.get_db()

    # Create beliefs
    beliefs_extended.add_belief(conn, "Strong belief", 0.9, "domain")
    beliefs_extended.add_belief(conn, "Weak belief", 0.2, "domain")
    beliefs_extended.add_belief(conn, "Pattern belief", 0.6, "pattern")

    # Test category filter
    domain_beliefs = beliefs_extended.list_beliefs(conn, category="domain")
    assert len(domain_beliefs) == 2

    # Test min confidence filter
    strong_beliefs = beliefs_extended.list_beliefs(conn, min_confidence=0.8)
    assert len(strong_beliefs) == 1
    assert strong_beliefs[0]['confidence'] == 0.9

    # Test combined filters
    filtered = beliefs_extended.list_beliefs(conn, category="domain", min_confidence=0.5)
    assert len(filtered) == 1

    conn.close()


def test_update_belief_confidence(temp_db):
    """Test updating belief confidence with revision logging."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Update confidence
    beliefs_extended.update_belief_confidence(
        conn, belief_id, 0.7,
        "Test reason", "manual"
    )

    # Verify update
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['confidence'] == 0.7

    # Verify revision was logged
    revisions = conn.execute("""
        SELECT * FROM belief_revisions WHERE belief_id = ?
    """, (belief_id,)).fetchall()
    assert len(revisions) == 1
    assert revisions[0]['old_confidence'] == 0.5
    assert revisions[0]['new_confidence'] == 0.7
    assert revisions[0]['reason'] == "Test reason"
    assert revisions[0]['revision_type'] == "manual"

    conn.close()


def test_add_evidence_updates_confidence(temp_db):
    """Test that adding evidence updates belief confidence."""
    conn = database.get_db()

    # Create belief with 50/50 confidence
    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Add strong supporting evidence
    mem_id = memory_ops.add_memory("learning", "Strong evidence", skip_dedup=True)
    beliefs_extended.add_evidence(conn, belief_id, mem_id, "supports", 0.9)

    # Confidence should increase
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['confidence'] > 0.5

    # Add contradicting evidence
    mem_id2 = memory_ops.add_memory("learning", "Contradicting evidence", skip_dedup=True)
    beliefs_extended.add_evidence(conn, belief_id, mem_id2, "contradicts", 0.7)

    # Confidence should decrease somewhat
    belief = beliefs_extended.get_belief(conn, belief_id)
    # Can't assert exact value due to complex formula, but should be between 0.3 and 0.7
    assert 0.3 < belief['confidence'] < 0.7

    conn.close()


def test_bayesian_update_supports(temp_db):
    """Test Bayesian update with supporting evidence."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Add strong supporting evidence using Bayesian update
    new_conf = beliefs_extended.bayesian_update(conn, belief_id, "supports", 0.8)

    # Formula: old * strength / (old * strength + (1-old) * (1-strength))
    # 0.5 * 0.8 / (0.5 * 0.8 + 0.5 * 0.2) = 0.4 / 0.5 = 0.8
    assert pytest.approx(new_conf, 0.01) == 0.8

    conn.close()


def test_bayesian_update_contradicts(temp_db):
    """Test Bayesian update with contradicting evidence."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.7)

    # Add strong contradicting evidence
    new_conf = beliefs_extended.bayesian_update(conn, belief_id, "contradicts", 0.8)

    # Formula: old * (1-strength) / (old * (1-strength) + (1-old) * strength)
    # 0.7 * 0.2 / (0.7 * 0.2 + 0.3 * 0.8) = 0.14 / 0.38 ≈ 0.368
    assert pytest.approx(new_conf, 0.01) == 0.368

    conn.close()


def test_make_prediction_from_belief(temp_db):
    """Test creating a prediction linked to a belief."""
    conn = database.get_db()

    # Create belief
    belief_id = beliefs_extended.add_belief(conn, "The feature will work", 0.8)

    # Make prediction
    deadline = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    pred_id = beliefs_extended.make_prediction(
        conn, belief_id,
        "Feature will pass all tests",
        confidence=0.75,
        deadline=deadline
    )

    assert pred_id > 0

    # Verify prediction
    pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
    assert pred is not None
    assert pred['confidence'] == 0.75
    assert pred['deadline'] == deadline
    assert pred['status'] == 'open'

    conn.close()


def test_resolve_prediction_updates_belief(temp_db):
    """Test that resolving a prediction updates the associated belief."""
    conn = database.get_db()

    # Create memory and belief
    mem_id = memory_ops.add_memory("belief", "Feature will work", skip_dedup=True)
    belief_id = beliefs_extended.add_belief(conn, "Feature will work", 0.6, memory_id=mem_id)

    # Make prediction
    pred_id = beliefs_extended.make_prediction(conn, belief_id, "Test prediction", 0.6)

    # Resolve as correct
    result = beliefs_extended.resolve_prediction_belief(conn, pred_id, "It worked!", True)

    assert result['updated_beliefs'] >= 1
    assert belief_id in result['belief_ids']

    # Belief confidence should have increased
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['confidence'] > 0.6

    conn.close()


def test_check_expired_predictions(temp_db):
    """Test detecting expired predictions."""
    conn = database.get_db()

    # Create belief
    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Create expired prediction
    past_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    pred1 = beliefs_extended.make_prediction(conn, belief_id, "Expired", deadline=past_date)

    # Create future prediction
    future_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    pred2 = beliefs_extended.make_prediction(conn, belief_id, "Future", deadline=future_date)

    # Check expired
    expired = beliefs_extended.check_expired_predictions(conn)
    assert len(expired) == 1
    assert expired[0]['id'] == pred1

    conn.close()


def test_detect_contradictions(temp_db):
    """Test contradiction detection between beliefs."""
    conn = database.get_db()

    # Create belief
    beliefs_extended.add_belief(conn, "The system is fast", 0.8)

    # Check for contradiction with similar but negated statement
    conflicts = beliefs_extended.detect_contradictions(conn, "The system is not fast")

    assert len(conflicts) >= 1
    assert conflicts[0]['similarity'] > 0.7

    conn.close()


def test_resolve_contradiction(temp_db):
    """Test resolving contradictions between beliefs."""
    conn = database.get_db()

    # Create contradicting beliefs
    belief1 = beliefs_extended.add_belief(conn, "Feature A works", 0.9)
    belief2 = beliefs_extended.add_belief(conn, "Feature A doesn't work", 0.8)

    # Resolve contradiction (keep belief1)
    beliefs_extended.resolve_contradiction(conn, belief1, belief2)

    # Verify belief2 is marked as disproven
    belief2_updated = beliefs_extended.get_belief(conn, belief2)
    assert belief2_updated['status'] == 'disproven'
    assert belief2_updated['confidence'] == 0.01

    conn.close()


def test_decay_beliefs(temp_db):
    """Test belief decay for inactive beliefs."""
    conn = database.get_db()

    # Create old belief with no evidence
    old_date = (datetime.now() - timedelta(days=100)).isoformat()
    belief_id = beliefs_extended.add_belief(conn, "Old belief", 0.7)
    conn.execute("""
        UPDATE beliefs SET updated_at = ? WHERE id = ?
    """, (old_date, belief_id))
    conn.commit()

    # Run decay
    decayed = beliefs_extended.decay_beliefs(conn, days_inactive=90)

    assert decayed >= 1

    # Belief should have lower confidence
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['confidence'] < 0.7

    conn.close()


def test_belief_accuracy_stats(temp_db):
    """Test belief accuracy calculation."""
    conn = database.get_db()

    # Create beliefs and predictions
    belief1 = beliefs_extended.add_belief(conn, "Belief 1", 0.8)
    belief2 = beliefs_extended.add_belief(conn, "Belief 2", 0.6)

    pred1 = beliefs_extended.make_prediction(conn, belief1, "Pred 1", 0.8)
    pred2 = beliefs_extended.make_prediction(conn, belief2, "Pred 2", 0.6)

    # Resolve predictions
    conn.execute("""
        UPDATE predictions SET status = 'confirmed', actual_outcome = 'worked'
        WHERE id = ?
    """, (pred1,))

    conn.execute("""
        UPDATE predictions SET status = 'refuted', actual_outcome = 'failed'
        WHERE id = ?
    """, (pred2,))
    conn.commit()

    # Get accuracy stats
    acc = beliefs_extended.belief_accuracy(conn)

    assert acc['total_predictions'] == 2
    assert acc['correct_count'] == 1
    assert acc['incorrect_count'] == 1
    assert acc['correct_percentage'] == 50.0

    conn.close()


def test_strongest_and_weakest_beliefs(temp_db):
    """Test retrieving strongest and weakest beliefs."""
    conn = database.get_db()

    # Create beliefs with varying confidence
    beliefs_extended.add_belief(conn, "Very strong", 0.95)
    beliefs_extended.add_belief(conn, "Medium", 0.5)
    beliefs_extended.add_belief(conn, "Very weak", 0.15)

    # Test strongest
    strong = beliefs_extended.strongest_beliefs_extended(conn, 2)
    assert len(strong) >= 1
    assert strong[0]['confidence'] >= 0.9

    # Test weakest
    weak = beliefs_extended.weakest_beliefs_extended(conn, 2)
    assert len(weak) >= 1
    assert weak[0]['confidence'] <= 0.2

    conn.close()


def test_most_revised_beliefs(temp_db):
    """Test finding beliefs with most revisions."""
    conn = database.get_db()

    belief1 = beliefs_extended.add_belief(conn, "Revised belief", 0.5)
    belief2 = beliefs_extended.add_belief(conn, "Stable belief", 0.6)

    # Make multiple revisions to belief1
    for i in range(5):
        beliefs_extended.update_belief_confidence(
            conn, belief1, 0.5 + i * 0.05,
            f"Update {i}", "manual"
        )

    # belief2 stays unchanged

    # Get most revised
    revised = beliefs_extended.most_revised(conn, 5)

    assert len(revised) >= 2
    # belief1 should be first (most revisions)
    assert revised[0]['id'] == belief1
    assert revised[0]['revision_count'] >= 5

    conn.close()


def test_search_beliefs(temp_db):
    """Test searching beliefs by statement text."""
    conn = database.get_db()

    beliefs_extended.add_belief(conn, "The database is fast", 0.8)
    beliefs_extended.add_belief(conn, "The API is slow", 0.6)
    beliefs_extended.add_belief(conn, "The cache improves speed", 0.7)

    # Search for "fast"
    results = beliefs_extended.search_beliefs(conn, "fast")
    assert len(results) == 1
    assert "fast" in results[0]['statement'].lower()

    # Search for "slow"
    results = beliefs_extended.search_beliefs(conn, "slow")
    assert len(results) == 1

    # Search for "speed"
    results = beliefs_extended.search_beliefs(conn, "speed")
    assert len(results) == 1

    conn.close()


def test_confidence_clamping(temp_db):
    """Test that confidence values are clamped to 0.01-0.99."""
    conn = database.get_db()

    # Try to create belief with too high confidence
    belief1 = beliefs_extended.add_belief(conn, "Test 1", 1.5)
    belief1_data = beliefs_extended.get_belief(conn, belief1)
    assert belief1_data['confidence'] == 0.99

    # Try to create belief with too low confidence
    belief2 = beliefs_extended.add_belief(conn, "Test 2", -0.5)
    belief2_data = beliefs_extended.get_belief(conn, belief2)
    assert belief2_data['confidence'] == 0.01

    # Try to update with invalid confidence
    beliefs_extended.update_belief_confidence(conn, belief1, 2.0, "test", "manual")
    belief1_data = beliefs_extended.get_belief(conn, belief1)
    assert belief1_data['confidence'] == 0.99

    conn.close()


def test_evidence_counters(temp_db):
    """Test that evidence counters are updated correctly."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(conn, "Test belief", 0.5)

    # Add multiple supporting evidence
    for i in range(3):
        mem_id = memory_ops.add_memory("learning", f"Support {i}", skip_dedup=True)
        beliefs_extended.add_evidence(conn, belief_id, mem_id, "supports", 0.7)

    # Add contradicting evidence
    for i in range(2):
        mem_id = memory_ops.add_memory("learning", f"Contradict {i}", skip_dedup=True)
        beliefs_extended.add_evidence(conn, belief_id, mem_id, "contradicts", 0.5)

    # Check counters
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['evidence_for'] == 3
    assert belief['evidence_against'] == 2

    conn.close()


def test_integration_with_memory_system(temp_db):
    """Test that beliefs can be linked to memories."""
    conn = database.get_db()

    # Create memory first
    mem_id = memory_ops.add_memory("belief", "System is scalable", skip_dedup=True)

    # Create belief linked to memory
    belief_id = beliefs_extended.add_belief(
        conn, "System is scalable",
        confidence=0.7,
        memory_id=mem_id
    )

    # Verify link
    belief = beliefs_extended.get_belief(conn, belief_id)
    assert belief['memory_id'] == mem_id

    # Verify memory exists
    memory = memory_ops.get_memory(mem_id)
    assert memory is not None

    conn.close()


def test_belief_revisions_tracking(temp_db):
    """Test that all belief revisions are tracked with type."""
    conn = database.get_db()

    belief_id = beliefs_extended.add_belief(conn, "Test", 0.5)

    # Manual update
    beliefs_extended.update_belief_confidence(conn, belief_id, 0.6, "Manual change", "manual")

    # Evidence update
    mem_id = memory_ops.add_memory("learning", "Evidence", skip_dedup=True)
    beliefs_extended.add_evidence(conn, belief_id, mem_id, "supports", 0.7)

    # Decay
    beliefs_extended.update_belief_confidence(conn, belief_id, 0.55, "Decay", "decay")

    # Check revisions
    revisions = conn.execute("""
        SELECT * FROM belief_revisions WHERE belief_id = ? ORDER BY created_at
    """, (belief_id,)).fetchall()

    assert len(revisions) >= 3
    assert any(r['revision_type'] == 'manual' for r in revisions)
    assert any(r['revision_type'] == 'evidence' for r in revisions)
    assert any(r['revision_type'] == 'decay' for r in revisions)

    conn.close()
