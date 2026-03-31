"""Tests for temporal timeline view (Feature 2)."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import database, beliefs, beliefs_extended


def test_log_confidence_change(temp_db):
    """Test logging confidence changes to timeline."""
    conn = database.get_db()

    # Create a belief
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence)
        VALUES (?, ?)
    """, ("Test belief", 0.5))
    belief_id = cursor.lastrowid
    conn.commit()

    # Log a confidence change
    beliefs_extended.log_confidence_change(
        conn,
        belief_id=belief_id,
        old_confidence=0.5,
        new_confidence=0.7,
        reason="Test reason",
        source_type="manual"
    )

    # Verify it was logged
    entries = conn.execute("""
        SELECT * FROM belief_timeline WHERE belief_id = ?
    """, (belief_id,)).fetchall()

    assert len(entries) == 1
    assert entries[0]['old_confidence'] == 0.5
    assert entries[0]['new_confidence'] == 0.7
    assert entries[0]['reason'] == "Test reason"
    assert entries[0]['source_type'] == "manual"

    conn.close()


def test_get_timeline_by_belief(temp_db):
    """Test retrieving timeline for a specific belief."""
    conn = database.get_db()

    # Create a belief
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence)
        VALUES (?, ?)
    """, ("Test belief", 0.5))
    belief_id = cursor.lastrowid
    conn.commit()

    # Log multiple changes
    beliefs_extended.log_confidence_change(
        conn, belief_id=belief_id,
        old_confidence=0.5, new_confidence=0.6,
        reason="First change", source_type="manual"
    )

    beliefs_extended.log_confidence_change(
        conn, belief_id=belief_id,
        old_confidence=0.6, new_confidence=0.8,
        reason="Second change", source_type="evidence"
    )

    # Get timeline
    timeline = beliefs_extended.get_timeline(conn, belief_id=belief_id, days=7)

    assert len(timeline) == 2
    # Check that both reasons are present (order may vary due to same timestamp)
    reasons = [t['reason'] for t in timeline]
    assert "First change" in reasons
    assert "Second change" in reasons

    conn.close()


def test_get_timeline_by_project(temp_db):
    """Test filtering timeline by project."""
    conn = database.get_db()

    # Create memories in different projects
    cursor = conn.execute("""
        INSERT INTO memories (category, content, project)
        VALUES (?, ?, ?)
    """, ("learning", "Memory 1", "ProjectA"))
    mem_id_a = cursor.lastrowid

    cursor = conn.execute("""
        INSERT INTO memories (category, content, project)
        VALUES (?, ?, ?)
    """, ("learning", "Memory 2", "ProjectB"))
    mem_id_b = cursor.lastrowid
    conn.commit()

    # Log changes for both
    beliefs_extended.log_confidence_change(
        conn, memory_id=mem_id_a,
        old_confidence=0.5, new_confidence=0.7,
        reason="Change in ProjectA", source_type="manual"
    )

    beliefs_extended.log_confidence_change(
        conn, memory_id=mem_id_b,
        old_confidence=0.4, new_confidence=0.6,
        reason="Change in ProjectB", source_type="manual"
    )

    # Get timeline for ProjectA only
    timeline_a = beliefs_extended.get_timeline(conn, project="ProjectA", days=7)
    assert len(timeline_a) == 1
    assert timeline_a[0]['memory_project'] == "ProjectA"

    # Get timeline for ProjectB only
    timeline_b = beliefs_extended.get_timeline(conn, project="ProjectB", days=7)
    assert len(timeline_b) == 1
    assert timeline_b[0]['memory_project'] == "ProjectB"

    conn.close()


def test_get_confidence_history_for_belief(temp_db):
    """Test getting full confidence history for a belief."""
    conn = database.get_db()

    # Create a belief
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence)
        VALUES (?, ?)
    """, ("Test belief", 0.5))
    belief_id = cursor.lastrowid
    conn.commit()

    # Make several confidence updates
    beliefs_extended.update_belief_confidence(
        conn, belief_id, 0.6, "First update", "manual"
    )

    beliefs_extended.update_belief_confidence(
        conn, belief_id, 0.7, "Second update", "evidence"
    )

    beliefs_extended.update_belief_confidence(
        conn, belief_id, 0.9, "Third update", "prediction_outcome"
    )

    # Get history
    history = beliefs_extended.get_confidence_history(conn, belief_id, is_belief=True)

    assert len(history) >= 3  # At least 3 updates

    # Check chronological order (oldest first)
    confidences = [h['new_confidence'] for h in history]
    assert 0.6 in confidences
    assert 0.7 in confidences
    assert 0.9 in confidences

    conn.close()


def test_get_confidence_history_for_memory(temp_db):
    """Test getting full confidence history for a memory."""
    conn = database.get_db()

    # Create a memory
    cursor = conn.execute("""
        INSERT INTO memories (category, content, confidence)
        VALUES (?, ?, ?)
    """, ("learning", "Test memory", 0.5))
    mem_id = cursor.lastrowid
    conn.commit()

    # Make several confidence updates using the beliefs system
    beliefs.set_confidence(conn, mem_id, 0.6, "First update")
    beliefs.set_confidence(conn, mem_id, 0.7, "Second update")
    beliefs.set_confidence(conn, mem_id, 0.8, "Third update")

    # Get history
    history = beliefs_extended.get_confidence_history(conn, mem_id, is_belief=False)

    assert len(history) >= 3  # At least 3 updates

    conn.close()


def test_format_timeline_entry_arrows(temp_db):
    """Test that timeline formatting shows correct arrow directions."""
    conn = database.get_db()

    # Test increase (↑)
    entry_up = {
        'timestamp': '2026-01-01 12:00',
        'old_confidence': 0.5,
        'new_confidence': 0.8,
        'reason': 'Increased',
        'source_type': 'evidence'
    }
    formatted_up = beliefs_extended.format_timeline_entry(entry_up)
    assert "↑" in formatted_up
    assert "0.50" in formatted_up
    assert "0.80" in formatted_up

    # Test decrease (↓)
    entry_down = {
        'timestamp': '2026-01-01 12:00',
        'old_confidence': 0.8,
        'new_confidence': 0.5,
        'reason': 'Decreased',
        'source_type': 'decay'
    }
    formatted_down = beliefs_extended.format_timeline_entry(entry_down)
    assert "↓" in formatted_down

    # Test no change (→)
    entry_same = {
        'timestamp': '2026-01-01 12:00',
        'old_confidence': 0.7,
        'new_confidence': 0.7,
        'reason': 'No change',
        'source_type': 'manual'
    }
    formatted_same = beliefs_extended.format_timeline_entry(entry_same)
    assert "→" in formatted_same

    conn.close()


def test_get_timeline_summary(temp_db):
    """Test timeline summary statistics."""
    conn = database.get_db()

    # Create some timeline entries with more increase than decrease
    for i in range(7):
        beliefs_extended.log_confidence_change(
            conn,
            belief_id=None,
            memory_id=None,
            old_confidence=0.5,
            new_confidence=0.7,
            reason=f"Increase {i}",
            source_type="evidence"
        )

    for i in range(2):
        beliefs_extended.log_confidence_change(
            conn,
            belief_id=None,
            memory_id=None,
            old_confidence=0.7,
            new_confidence=0.5,
            reason=f"Decrease {i}",
            source_type="decay"
        )

    # Get summary
    summary = beliefs_extended.get_timeline_summary(conn, days=7)

    assert summary['total_changes'] == 9
    assert summary['increases'] == 7
    assert summary['decreases'] == 2
    # 7 increases of +0.2, 2 decreases of -0.2 = avg of (1.4 - 0.4) / 9 ≈ 0.11
    assert summary['avg_confidence_delta'] > 0  # More increases than decreases

    # Check by_source
    assert len(summary['by_source']) > 0
    source_types = [s['source_type'] for s in summary['by_source']]
    assert 'evidence' in source_types
    assert 'decay' in source_types

    conn.close()


def test_timeline_filtering_by_days(temp_db):
    """Test that timeline respects the days parameter."""
    conn = database.get_db()

    # Create an old entry (beyond 7 days)
    old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO belief_timeline (belief_id, old_confidence, new_confidence, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (None, 0.5, 0.7, "Old change", old_date))

    # Create a recent entry
    beliefs_extended.log_confidence_change(
        conn,
        belief_id=None,
        old_confidence=0.6,
        new_confidence=0.8,
        reason="Recent change",
        source_type="manual"
    )

    # Get timeline for last 7 days
    timeline_7d = beliefs_extended.get_timeline(conn, days=7)
    assert len(timeline_7d) == 1
    assert timeline_7d[0]['reason'] == "Recent change"

    # Get timeline for last 30 days
    timeline_30d = beliefs_extended.get_timeline(conn, days=30)
    assert len(timeline_30d) == 2  # Both entries

    conn.close()


def test_timeline_integrated_with_confidence_updates(temp_db):
    """Test that confidence updates automatically create timeline entries."""
    conn = database.get_db()

    # Create a belief
    cursor = conn.execute("""
        INSERT INTO beliefs (statement, confidence)
        VALUES (?, ?)
    """, ("Test belief", 0.5))
    belief_id = cursor.lastrowid
    conn.commit()

    # Update confidence (should auto-log to timeline)
    beliefs_extended.update_belief_confidence(
        conn, belief_id, 0.8, "Automatic logging test", "manual"
    )

    # Check that timeline entry was created
    timeline = beliefs_extended.get_timeline(conn, belief_id=belief_id, days=1)
    assert len(timeline) >= 1

    # Find the entry
    entry = next((e for e in timeline if e['reason'] == "Automatic logging test"), None)
    assert entry is not None
    assert entry['old_confidence'] == 0.5
    assert entry['new_confidence'] == 0.8

    conn.close()
