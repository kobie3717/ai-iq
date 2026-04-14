"""Tests for reasoning boost display indicators."""

import pytest
import sqlite3
from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import add_memory, search_memories
from memory_tool.beliefs import predict, resolve_prediction_memory
from memory_tool.display import format_row_compact


@pytest.fixture
def db(temp_db):
    """Test database fixture."""
    return temp_db


def test_reasoning_indicator_confirmed(db):
    """Test that confirmed predictions show ✓ indicator."""
    # Create memory with confirmed prediction
    mem_id = add_memory(
        'learning',
        'Rate limiting prevents API abuse',
        tags='api,security'
    )

    pred_id = predict(
        db,
        prediction='Abuse will decrease',
        based_on=mem_id,
        confidence=0.8
    )

    resolve_prediction_memory(db, pred_id, 'Abuse dropped 70%', confirmed=True)

    # Get the memory row
    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()

    # Format and check for indicator
    formatted = format_row_compact(row)
    assert '[✓ confirmed]' in formatted, f"Expected confirmed indicator in: {formatted}"


def test_reasoning_indicator_refuted(db):
    """Test that refuted predictions show ✗ indicator."""
    mem_id = add_memory(
        'learning',
        'Caching solves all performance issues',
        tags='performance'
    )

    pred_id = predict(
        db,
        prediction='Response times will improve 90%',
        based_on=mem_id,
        confidence=0.9
    )

    resolve_prediction_memory(db, pred_id, 'Only improved 10%', confirmed=False)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)
    assert '[✗ refuted]' in formatted, f"Expected refuted indicator in: {formatted}"


def test_reasoning_indicator_mixed(db):
    """Test that mixed predictions show ± indicator with counts."""
    mem_id = add_memory(
        'learning',
        'TypeScript improves code quality',
        tags='typescript'
    )

    pred1 = predict(db, 'Fewer runtime errors', based_on=mem_id, confidence=0.7)
    pred2 = predict(db, 'Zero bugs ever', based_on=mem_id, confidence=0.9)

    resolve_prediction_memory(db, pred1, 'Errors down 40%', confirmed=True)
    resolve_prediction_memory(db, pred2, 'Still have bugs', confirmed=False)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)
    assert '[±1/1]' in formatted, f"Expected mixed indicator in: {formatted}"


def test_reasoning_indicator_none(db):
    """Test that memories with no predictions show no indicator."""
    mem_id = add_memory(
        'learning',
        'PostgreSQL is a relational database',
        tags='database'
    )

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)

    # Should not have any reasoning indicators
    assert '[✓' not in formatted
    assert '[✗' not in formatted
    assert '[±' not in formatted


def test_reasoning_indicator_open_only(db):
    """Test that open predictions don't show indicator (only resolved ones)."""
    mem_id = add_memory(
        'learning',
        'Microservices scale better',
        tags='architecture'
    )

    # Create prediction but don't resolve it
    predict(db, 'Will scale well', based_on=mem_id, confidence=0.8)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)

    # Should not show indicator for unresolved predictions
    assert '[✓' not in formatted
    assert '[✗' not in formatted
    assert '[±' not in formatted


def test_reasoning_indicator_in_search_results(db):
    """Test that reasoning indicators appear in search results."""
    # Create two memories with different prediction outcomes
    mem_confirmed = add_memory('learning', 'Good practice works', tags='best')
    mem_refuted = add_memory('learning', 'Bad practice fails', tags='worst')

    pred1 = predict(db, 'Will succeed', based_on=mem_confirmed, confidence=0.8)
    pred2 = predict(db, 'Will fail', based_on=mem_refuted, confidence=0.7)

    resolve_prediction_memory(db, pred1, 'Success!', confirmed=True)
    resolve_prediction_memory(db, pred2, 'Failed', confirmed=False)

    # Search for both
    rows, _, _ = search_memories('practice', mode='keyword')

    # Format and check indicators appear
    formatted_outputs = [format_row_compact(r) for r in rows]
    combined = '\n'.join(formatted_outputs)

    assert '[✓ confirmed]' in combined, "Should show confirmed indicator in search results"
    assert '[✗ refuted]' in combined, "Should show refuted indicator in search results"


def test_reasoning_indicator_multiple_confirmed(db):
    """Test indicator with multiple confirmed predictions."""
    mem_id = add_memory('learning', 'Best practice confirmed multiple times', tags='best')

    pred1 = predict(db, 'First success', based_on=mem_id, confidence=0.8)
    pred2 = predict(db, 'Second success', based_on=mem_id, confidence=0.9)

    resolve_prediction_memory(db, pred1, 'Worked', confirmed=True)
    resolve_prediction_memory(db, pred2, 'Also worked', confirmed=True)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)

    # Should show confirmed (all predictions confirmed)
    assert '[✓ confirmed]' in formatted


def test_reasoning_indicator_multiple_refuted(db):
    """Test indicator with multiple refuted predictions."""
    mem_id = add_memory('learning', 'Bad practice refuted multiple times', tags='bad')

    pred1 = predict(db, 'First failure', based_on=mem_id, confidence=0.6)
    pred2 = predict(db, 'Second failure', based_on=mem_id, confidence=0.7)

    resolve_prediction_memory(db, pred1, 'Failed', confirmed=False)
    resolve_prediction_memory(db, pred2, 'Also failed', confirmed=False)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)

    # Should show refuted (all predictions refuted)
    assert '[✗ refuted]' in formatted


def test_reasoning_indicator_complex_mix(db):
    """Test indicator with complex mix: 3 confirmed, 2 refuted."""
    mem_id = add_memory('learning', 'Complex pattern with mixed results', tags='complex')

    for i in range(3):
        pred = predict(db, f'Confirmed {i}', based_on=mem_id, confidence=0.7)
        resolve_prediction_memory(db, pred, 'Success', confirmed=True)

    for i in range(2):
        pred = predict(db, f'Refuted {i}', based_on=mem_id, confidence=0.6)
        resolve_prediction_memory(db, pred, 'Failed', confirmed=False)

    row = db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
    formatted = format_row_compact(row)

    # Should show ±3/2 (3 confirmed, 2 refuted)
    assert '[±3/2]' in formatted


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
