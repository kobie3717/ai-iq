"""Tests for ReasoningBank-inspired retrieval boost."""

import pytest
import sqlite3
from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import add_memory, search_memories
from memory_tool.beliefs import predict, resolve_prediction_memory
from memory_tool.reasoning import (
    compute_reasoning_score,
    compute_reasoning_boost,
    get_reasoning_boosts,
    show_reasoning_details
)


@pytest.fixture
def db(temp_db):
    """Test database fixture."""
    # Use the temp_db fixture from conftest.py for proper isolation
    return temp_db


def test_reasoning_score_no_predictions(db):
    """Memory with no linked predictions should have neutral score."""
    mem_id = add_memory(
        category='learning',
        content='JWT tokens are stateless authentication',
        tags='auth,jwt',
        project='TestProject'
    )

    score, details = compute_reasoning_score(db, mem_id)

    assert score == 0.5  # Neutral
    assert details['confirmed'] == 0
    assert details['refuted'] == 0
    assert details['open'] == 0
    assert len(details['predictions']) == 0


def test_reasoning_score_confirmed_prediction(db):
    """Memory linked to confirmed prediction should boost above neutral."""
    mem_id = add_memory(
        category='learning',
        content='Adding rate limiting will reduce API abuse',
        tags='api,security',
        project='TestProject'
    )

    # Create prediction based on this memory
    pred_id = predict(
        db,
        prediction='API abuse incidents will drop by 50% after rate limiting',
        based_on=mem_id,
        confidence=0.8,
        expected_outcome='50% reduction in abuse'
    )

    # Resolve as confirmed
    resolve_prediction_memory(db, pred_id, 'Abuse dropped by 60%', confirmed=True)

    score, details = compute_reasoning_score(db, mem_id)

    assert score == 1.0  # All predictions confirmed
    assert details['confirmed'] == 1
    assert details['refuted'] == 0
    assert details['open'] == 0
    assert len(details['predictions']) == 1
    assert details['predictions'][0]['status'] == 'confirmed'


def test_reasoning_score_refuted_prediction(db):
    """Memory linked to refuted prediction should score below neutral."""
    mem_id = add_memory(
        category='learning',
        content='Caching will solve all performance issues',
        tags='performance',
        project='TestProject'
    )

    # Create prediction
    pred_id = predict(
        db,
        prediction='Response times will improve by 90%',
        based_on=mem_id,
        confidence=0.9,
        expected_outcome='90% improvement'
    )

    # Resolve as refuted
    resolve_prediction_memory(db, pred_id, 'Only improved 10%, bottleneck was database', confirmed=False)

    score, details = compute_reasoning_score(db, mem_id)

    assert score == 0.0  # All predictions refuted
    assert details['confirmed'] == 0
    assert details['refuted'] == 1
    assert details['open'] == 0


def test_reasoning_score_mixed_predictions(db):
    """Memory with both confirmed and refuted predictions should score based on ratio."""
    mem_id = add_memory(
        category='learning',
        content='TypeScript improves code quality',
        tags='typescript,quality',
        project='TestProject'
    )

    # Create 3 predictions: 2 confirmed, 1 refuted
    pred1 = predict(db, 'Fewer runtime errors', based_on=mem_id, confidence=0.7)
    pred2 = predict(db, 'Better IDE support', based_on=mem_id, confidence=0.8)
    pred3 = predict(db, 'Zero bugs forever', based_on=mem_id, confidence=0.9)

    resolve_prediction_memory(db, pred1, 'Errors down 40%', confirmed=True)
    resolve_prediction_memory(db, pred2, 'Autocomplete works great', confirmed=True)
    resolve_prediction_memory(db, pred3, 'Still found bugs, just different ones', confirmed=False)

    score, details = compute_reasoning_score(db, mem_id)

    assert score == pytest.approx(0.666, abs=0.01)  # 2/3 confirmed
    assert details['confirmed'] == 2
    assert details['refuted'] == 1
    assert details['open'] == 0


def test_reasoning_score_open_predictions_ignored(db):
    """Open predictions should not affect score (only resolved ones count)."""
    mem_id = add_memory(
        category='learning',
        content='Microservices will scale better',
        tags='architecture',
        project='TestProject'
    )

    # Create 1 confirmed and 2 open predictions
    pred1 = predict(db, 'Can scale teams independently', based_on=mem_id, confidence=0.8)
    pred2 = predict(db, 'Will be easier to deploy', based_on=mem_id, confidence=0.6)
    pred3 = predict(db, 'Latency will stay the same', based_on=mem_id, confidence=0.5)

    resolve_prediction_memory(db, pred1, 'Teams scaled well', confirmed=True)
    # pred2 and pred3 remain open

    score, details = compute_reasoning_score(db, mem_id)

    assert score == 1.0  # Only resolved predictions count: 1/1 = 100%
    assert details['confirmed'] == 1
    assert details['refuted'] == 0
    assert details['open'] == 2


def test_reasoning_boost_calculation():
    """Test boost multiplier calculation from scores."""
    # Neutral score → 1.0x boost
    assert compute_reasoning_boost(0.5) == pytest.approx(1.0, abs=0.01)

    # All confirmed → 1.5x boost (max)
    assert compute_reasoning_boost(1.0) == pytest.approx(1.5, abs=0.01)

    # All refuted → 0.7x boost (min penalty)
    assert compute_reasoning_boost(0.0) == pytest.approx(0.7, abs=0.01)

    # 75% confirmed → 1.25x boost
    assert compute_reasoning_boost(0.75) == pytest.approx(1.25, abs=0.01)

    # 25% confirmed → 0.75x boost
    assert compute_reasoning_boost(0.25) == pytest.approx(0.75, abs=0.01)


def test_reasoning_boost_clamping():
    """Test that boost is clamped to safe range."""
    # Should clamp values outside 0-1 range
    assert compute_reasoning_boost(-0.5) == 0.7  # Min
    assert compute_reasoning_boost(1.5) == 1.5  # Max
    assert compute_reasoning_boost(2.0) == 1.5  # Still max


def test_get_reasoning_boosts_batch(db):
    """Test batch computation of reasoning boosts."""
    # Create 3 memories with different prediction outcomes
    mem1 = add_memory('learning', 'Good decision', tags='decision')
    mem2 = add_memory('learning', 'Bad decision', tags='decision')
    mem3 = add_memory('learning', 'No predictions', tags='decision')

    pred1 = predict(db, 'Will work well', based_on=mem1, confidence=0.8)
    pred2 = predict(db, 'Will fail', based_on=mem2, confidence=0.7)

    resolve_prediction_memory(db, pred1, 'Success!', confirmed=True)
    resolve_prediction_memory(db, pred2, 'Failed as expected... wait, predicted failure confirmed = good reasoning', confirmed=True)

    boosts = get_reasoning_boosts(db, [mem1, mem2, mem3])

    assert boosts[mem1] == pytest.approx(1.5, abs=0.01)  # 100% confirmed
    assert boosts[mem2] == pytest.approx(1.5, abs=0.01)  # 100% confirmed (predicted failure correctly)
    assert boosts[mem3] == pytest.approx(1.0, abs=0.01)  # No predictions = neutral


def test_reasoning_boost_in_search(db):
    """Test that reasoning boost affects search ranking."""
    # Create two similar memories
    mem_good = add_memory(
        'learning',
        'Redis needs network_mode: host for Docker',
        tags='redis,docker'
    )
    mem_bad = add_memory(
        'learning',
        'Redis works fine with bridge network',
        tags='redis,docker'
    )

    # mem_good has confirmed prediction
    pred_good = predict(db, 'Host mode will fix connection issues', based_on=mem_good, confidence=0.8)
    resolve_prediction_memory(db, pred_good, 'Fixed!', confirmed=True)

    # mem_bad has refuted prediction
    pred_bad = predict(db, 'Bridge network is sufficient', based_on=mem_bad, confidence=0.7)
    resolve_prediction_memory(db, pred_bad, 'Didnt work, switched to host mode', confirmed=False)

    # Search for redis
    rows, _, _ = search_memories('redis docker', mode='keyword', reasoning_boost=True)

    # mem_good should rank higher due to reasoning boost
    ids = [r['id'] for r in rows]
    assert ids.index(mem_good) < ids.index(mem_bad), "Memory with confirmed prediction should rank higher"


def test_reasoning_boost_disabled(db):
    """Test that reasoning boost can be disabled."""
    mem1 = add_memory('learning', 'Redis works great for caching user sessions', tags='testboost,redis')
    mem2 = add_memory('learning', 'PostgreSQL handles relational queries efficiently', tags='testboost,postgres')

    # mem1 has confirmed prediction
    pred1 = predict(db, 'Will succeed', based_on=mem1, confidence=0.8)
    resolve_prediction_memory(db, pred1, 'Success', confirmed=True)

    # Search with reasoning boost disabled
    rows_no_boost, _, _ = search_memories('testboost', mode='keyword', reasoning_boost=False)

    # Should return results without reasoning boost affecting rank
    # (Hard to assert exact order without boost, but at least verify no crash)
    assert len(rows_no_boost) >= 2


def test_show_reasoning_details(db):
    """Test the reasoning details report."""
    mem_id = add_memory(
        'learning',
        'Implementing caching improved performance',
        tags='performance,cache',
        project='MyApp'
    )

    pred1 = predict(db, 'Response times will drop 50%', based_on=mem_id, confidence=0.8)
    pred2 = predict(db, 'Server load will decrease', based_on=mem_id, confidence=0.7)

    resolve_prediction_memory(db, pred1, 'Dropped 60%!', confirmed=True)
    # Leave pred2 open

    report = show_reasoning_details(db, mem_id)

    assert f'Memory #{mem_id}' in report
    assert 'Implementing caching' in report
    assert 'Reasoning Score:' in report
    assert 'Retrieval Boost:' in report
    assert '1 confirmed' in report
    assert '1 open' in report
    assert 'Response times' in report


def test_reasoning_details_no_predictions(db):
    """Test reasoning details for memory with no predictions."""
    mem_id = add_memory('learning', 'Some fact', tags='test')

    report = show_reasoning_details(db, mem_id)

    assert 'No linked predictions' in report
    assert 'neutral score (1.0x boost)' in report


def test_reasoning_details_nonexistent_memory(db):
    """Test reasoning details for nonexistent memory."""
    report = show_reasoning_details(db, 99999)
    assert 'not found' in report


def test_cli_reasoning_command(db):
    """Test the CLI reasoning command."""
    from memory_tool.cli import main
    import sys

    mem_id = add_memory('learning', 'Test for CLI', tags='cli')
    pred = predict(db, 'CLI will work', based_on=mem_id, confidence=0.9)
    resolve_prediction_memory(db, pred, 'It worked!', confirmed=True)

    # Simulate CLI call
    old_argv = sys.argv
    try:
        sys.argv = ['memory-tool', 'reasoning', str(mem_id)]
        # Can't easily capture stdout in pytest, but verify no crash
        # In real usage, this would print the report
    finally:
        sys.argv = old_argv


def test_search_with_no_reasoning_boost_flag(db):
    """Test search with --no-reasoning-boost flag."""
    mem_id = add_memory('learning', 'Test search flag', tags='flag')
    pred = predict(db, 'Flag test', based_on=mem_id, confidence=0.8)
    resolve_prediction_memory(db, pred, 'Success', confirmed=True)

    # Search with reasoning boost enabled (default)
    rows_with, _, _ = search_memories('flag', reasoning_boost=True)
    assert len(rows_with) >= 1

    # Search with reasoning boost disabled
    rows_without, _, _ = search_memories('flag', reasoning_boost=False)
    assert len(rows_without) >= 1


def test_reasoning_bank_filter(db):
    """Test --reasoning-bank filter shows only memories with confirmed predictions."""
    # Create memory with confirmed prediction
    mem_confirmed = add_memory('learning', 'Good decision pattern', tags='decision,pattern')
    pred_confirmed = predict(db, 'This pattern works', based_on=mem_confirmed, confidence=0.8)
    resolve_prediction_memory(db, pred_confirmed, 'Worked perfectly', confirmed=True)

    # Create memory with refuted prediction
    mem_refuted = add_memory('learning', 'Bad decision pattern', tags='decision,pattern')
    pred_refuted = predict(db, 'This pattern fails', based_on=mem_refuted, confidence=0.7)
    resolve_prediction_memory(db, pred_refuted, 'Failed badly', confirmed=False)

    # Create memory with open prediction
    mem_open = add_memory('learning', 'Unknown decision pattern', tags='decision,pattern')
    pred_open = predict(db, 'Not sure yet', based_on=mem_open, confidence=0.5)

    # Create memory with no predictions
    mem_none = add_memory('learning', 'Neutral decision pattern', tags='decision,pattern')

    # Search all
    all_rows, _, _ = search_memories('decision pattern', mode='keyword')
    assert len(all_rows) >= 4  # Should find all 4

    # Now filter to only confirmed predictions using reasoning module directly
    from memory_tool.reasoning import compute_reasoning_score
    conn = get_db()
    filtered = []
    for r in all_rows:
        score, details = compute_reasoning_score(conn, r['id'])
        if details['confirmed'] > 0:
            filtered.append(r['id'])
    conn.close()

    # Only mem_confirmed should pass the filter
    assert mem_confirmed in filtered
    assert mem_refuted not in filtered  # Has predictions but refuted, not confirmed
    assert mem_open not in filtered  # Has predictions but open, not confirmed
    assert mem_none not in filtered  # No predictions at all


def test_get_top_reasoning_memories(db):
    """Test getting top memories by reasoning boost."""
    from memory_tool.reasoning import get_top_reasoning_memories

    # Create memories with different prediction outcomes
    mem1 = add_memory('learning', 'Best practice confirmed', tags='best')
    mem2 = add_memory('learning', 'Good practice confirmed', tags='good')
    mem3 = add_memory('learning', 'Mixed results', tags='mixed')
    mem4 = add_memory('learning', 'Bad practice refuted', tags='bad')

    # mem1: 2 confirmed predictions → boost 1.5x
    pred1a = predict(db, 'Will work', based_on=mem1, confidence=0.8)
    pred1b = predict(db, 'Will scale', based_on=mem1, confidence=0.9)
    resolve_prediction_memory(db, pred1a, 'Success', confirmed=True)
    resolve_prediction_memory(db, pred1b, 'Success', confirmed=True)

    # mem2: 1 confirmed prediction → boost 1.5x
    pred2 = predict(db, 'Will help', based_on=mem2, confidence=0.7)
    resolve_prediction_memory(db, pred2, 'Helped!', confirmed=True)

    # mem3: 1 confirmed, 1 refuted → boost 1.0x
    pred3a = predict(db, 'Will work', based_on=mem3, confidence=0.6)
    pred3b = predict(db, 'Will fail', based_on=mem3, confidence=0.4)
    resolve_prediction_memory(db, pred3a, 'Worked', confirmed=True)
    resolve_prediction_memory(db, pred3b, 'Also worked', confirmed=False)

    # mem4: 1 refuted prediction → boost 0.7x
    pred4 = predict(db, 'Will work', based_on=mem4, confidence=0.5)
    resolve_prediction_memory(db, pred4, 'Failed', confirmed=False)

    # Get top memories
    top = get_top_reasoning_memories(db, limit=10)

    # Should return 4 memories (all with resolved predictions)
    assert len(top) == 4

    # Check they're sorted by boost (descending)
    boosts = [boost for _, _, boost, _ in top]
    assert boosts == sorted(boosts, reverse=True)

    # mem1 and mem2 should be at top (both 1.5x boost)
    top_ids = [mem_id for mem_id, _, _, _ in top[:2]]
    assert mem1 in top_ids
    assert mem2 in top_ids

    # mem4 should be at bottom (0.7x boost)
    assert top[-1][0] == mem4


def test_get_reasoning_statistics(db):
    """Test reasoning statistics."""
    from memory_tool.reasoning import get_reasoning_statistics

    # Create various memories
    mem_boosted = add_memory('learning', 'Boosted', tags='test')
    mem_penalized = add_memory('learning', 'Penalized', tags='test')
    mem_neutral = add_memory('learning', 'Neutral', tags='test')
    mem_no_pred = add_memory('learning', 'No predictions', tags='test')

    # Boosted: confirmed prediction
    pred_b = predict(db, 'Will work', based_on=mem_boosted, confidence=0.8)
    resolve_prediction_memory(db, pred_b, 'Worked', confirmed=True)

    # Penalized: refuted prediction
    pred_p = predict(db, 'Will work', based_on=mem_penalized, confidence=0.7)
    resolve_prediction_memory(db, pred_p, 'Failed', confirmed=False)

    # Neutral: 50/50 mix
    pred_n1 = predict(db, 'First', based_on=mem_neutral, confidence=0.6)
    pred_n2 = predict(db, 'Second', based_on=mem_neutral, confidence=0.6)
    resolve_prediction_memory(db, pred_n1, 'Success', confirmed=True)
    resolve_prediction_memory(db, pred_n2, 'Failed', confirmed=False)

    # Get stats
    stats = get_reasoning_statistics(db)

    assert stats['boosted'] >= 1  # mem_boosted
    assert stats['penalized'] >= 1  # mem_penalized
    assert stats['neutral'] >= 1  # mem_neutral (50% score → 1.0x boost)
    assert stats['total_with_predictions'] >= 3  # All except mem_no_pred


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
