"""Tests for ReasoningBank-style retrieval boost based on prediction outcomes."""

import pytest
import sqlite3
import uuid
from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import search_memories
from memory_tool.beliefs import predict, resolve_prediction_memory
from memory_tool.reasoning import (
    compute_reasoning_boost,
    get_memory_reasoning_stats,
    list_memories_by_reasoning,
    apply_reasoning_boost_to_scores
)


def unique_content(base: str) -> str:
    """Generate unique content to bypass duplicate detection."""
    return f"{base} [{uuid.uuid4().hex[:8]}]"


def insert_memory(content: str, category: str = "learning") -> int:
    """Insert memory directly bypassing duplicate detection."""
    from memory_tool.embedding import embed_and_store
    conn = get_db()
    mem_id = conn.execute(
        "INSERT INTO memories (category, content) VALUES (?, ?)",
        (category, content)
    ).lastrowid
    # Embed for search tests
    try:
        embed_and_store(conn, mem_id, content)
    except Exception:
        pass  # Embedding might not be available in all test environments
    conn.commit()
    conn.close()
    return mem_id


@pytest.fixture
def test_db(tmp_path):
    """Create a clean test database."""
    from memory_tool.config import DB_PATH
    import memory_tool.config as config

    # Override DB_PATH for tests
    test_db_path = tmp_path / "test_memories.db"
    config.DB_PATH = test_db_path

    # Initialize fresh database
    init_db()

    yield test_db_path

    # Cleanup
    if test_db_path.exists():
        test_db_path.unlink()


def test_compute_reasoning_boost_no_predictions(test_db):
    """Memory with no linked predictions gets boost of 1.0 (neutral)."""
    mem_id = insert_memory(unique_content("Test memory with no predictions"))

    boost = compute_reasoning_boost(mem_id)

    assert boost == 1.0


def test_compute_reasoning_boost_confirmed_predictions(test_db):
    """Memory with 2 confirmed predictions gets boost ≈ 2.25."""
    mem_id = insert_memory(unique_content("Memory that led to good predictions"))

    conn = get_db()
    # Create 2 confirmed predictions based on this memory
    pred1_id = predict(conn, "First prediction", mem_id, 0.8, None, "Expected outcome 1")
    pred2_id = predict(conn, "Second prediction", mem_id, 0.8, None, "Expected outcome 2")

    # Resolve both as confirmed
    resolve_prediction_memory(conn, pred1_id, "Outcome 1 confirmed", confirmed=True)
    resolve_prediction_memory(conn, pred2_id, "Outcome 2 confirmed", confirmed=True)
    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = 1.5^2 = 2.25, capped at 2.0
    assert boost == pytest.approx(2.0, rel=0.01)


def test_compute_reasoning_boost_refuted_predictions(test_db):
    """Memory with 1 refuted prediction gets boost ≈ 0.67."""
    mem_id = insert_memory(unique_content("Memory that led to a bad prediction"))

    conn = get_db()
    # Create 1 refuted prediction based on this memory
    pred_id = predict(conn, "Bad prediction", mem_id, 0.8, None, "Expected outcome")

    # Resolve as refuted
    resolve_prediction_memory(conn, pred_id, "Actually didn't happen", confirmed=False)
    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = 1.0 / 1.5 = 0.667...
    assert boost == pytest.approx(0.667, rel=0.01)


def test_compute_reasoning_boost_mixed_predictions(test_db):
    """Memory with 3 confirmed + 1 refuted gets boost = 2.0 (capped)."""
    mem_id = insert_memory(unique_content("Memory with mixed outcomes"))

    conn = get_db()

    # Create 3 confirmed predictions
    for i in range(3):
        pred_id = predict(conn, f"Good prediction {i}", mem_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    # Create 1 refuted prediction
    pred_id = predict(conn, "Bad prediction", mem_id, 0.8, None, "Expected bad")
    resolve_prediction_memory(conn, pred_id, "Refuted", confirmed=False)

    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = (1.5^3) / 1.5 = 1.5^2 = 2.25, capped at 2.0
    assert boost == pytest.approx(2.0, rel=0.01)


def test_compute_reasoning_boost_clamped_low(test_db):
    """Memory with 10 refuted predictions still clamps at 0.3 (not below)."""
    mem_id = insert_memory(unique_content("Memory with many bad predictions"))

    conn = get_db()

    # Create 10 refuted predictions
    for i in range(10):
        pred_id = predict(conn, f"Bad prediction {i}", mem_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Refuted {i}", confirmed=False)

    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = 1.0 / (1.3^10) = ~0.073, clamped to 0.3
    assert boost == pytest.approx(0.3, rel=0.01)


def test_compute_reasoning_boost_clamped_high(test_db):
    """Memory with 10 confirmed predictions clamps at REASONING_BOOST_CAP (1.8)."""
    from memory_tool.config import REASONING_BOOST_CAP

    mem_id = insert_memory(unique_content("Memory with many good predictions"))

    conn = get_db()

    # Create 10 confirmed predictions
    for i in range(10):
        pred_id = predict(conn, f"Good prediction {i}", mem_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = 1.3^10 = 13.79, clamped to REASONING_BOOST_CAP (1.8)
    assert boost == pytest.approx(REASONING_BOOST_CAP, rel=0.01)


def test_get_memory_reasoning_stats(test_db):
    """Get prediction statistics for a memory."""
    mem_id = insert_memory(unique_content("Memory for stats test"))

    conn = get_db()

    # Create predictions with different statuses
    pred1_id = predict(conn, "Pred 1", mem_id, 0.8, None, "Expected 1")
    pred2_id = predict(conn, "Pred 2", mem_id, 0.8, None, "Expected 2")
    pred3_id = predict(conn, "Pred 3", mem_id, 0.8, None, "Expected 3")

    resolve_prediction_memory(conn, pred1_id, "Confirmed", confirmed=True)
    resolve_prediction_memory(conn, pred2_id, "Refuted", confirmed=False)
    # pred3 left open

    conn.close()

    stats = get_memory_reasoning_stats(mem_id)

    assert stats['confirmed'] == 1
    assert stats['refuted'] == 1
    assert stats['open'] == 1
    assert stats['total'] == 3


def test_list_memories_by_reasoning(test_db):
    """List memories ranked by reasoning boost."""
    # Create 3 memories with different prediction outcomes
    mem1_id = insert_memory(unique_content("Memory with high boost"))
    mem2_id = insert_memory(unique_content("Memory with neutral boost"))
    mem3_id = insert_memory(unique_content("Memory with low boost"))

    conn = get_db()

    # mem1: 2 confirmed → boost 1.5^2 = 2.25, capped at 2.0
    for i in range(2):
        pred_id = predict(conn, f"Good pred {i}", mem1_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    # mem2: 1 confirmed, 1 refuted → boost 1.5 / 1.5 = 1.0
    pred_id = predict(conn, "Good pred", mem2_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)
    pred_id = predict(conn, "Bad pred", mem2_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Refuted", confirmed=False)

    # mem3: 1 refuted → boost 1.0 / 1.5 = 0.667
    pred_id = predict(conn, "Bad pred", mem3_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Refuted", confirmed=False)

    conn.close()

    results = list_memories_by_reasoning()

    # Filter to just our test memories
    test_mem_ids = {mem1_id, mem2_id, mem3_id}
    results = [r for r in results if r[0] in test_mem_ids]

    # Should be sorted by boost descending: mem1 (2.0 capped), mem2 (1.0), mem3 (0.667)
    assert len(results) == 3
    assert results[0][0] == mem1_id  # mem_id
    assert results[0][4] == pytest.approx(2.0, rel=0.01)  # boost (capped)
    assert results[1][0] == mem2_id
    assert results[1][4] == pytest.approx(1.0, rel=0.01)
    assert results[2][0] == mem3_id
    assert results[2][4] == pytest.approx(0.667, rel=0.01)


def test_apply_reasoning_boost_to_scores(test_db):
    """Apply reasoning boost to a score dictionary."""
    mem1_id = insert_memory(unique_content("Memory with boost"))
    mem2_id = insert_memory(unique_content("Memory without boost"))

    conn = get_db()

    # mem1: 2 confirmed → boost 1.5^2 = 2.25, capped at 2.0
    for i in range(2):
        pred_id = predict(conn, f"Good pred {i}", mem1_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    # mem2: no predictions → boost 1.0

    # Simulate search scores
    scores = {
        mem1_id: 100.0,
        mem2_id: 100.0
    }

    apply_reasoning_boost_to_scores(scores, conn)
    conn.close()

    # mem1 should be boosted by 2.0x (capped), mem2 stays same
    assert scores[mem1_id] == pytest.approx(200.0, rel=0.01)
    assert scores[mem2_id] == pytest.approx(100.0, rel=0.01)


def test_reasoning_boost_in_search(test_db):
    """Search with reasoning boost ranks high-confirmed memory higher."""
    # Skip this test if vector search is not available
    from memory_tool.database import has_vec_support
    if not has_vec_support():
        pytest.skip("Vector search not available")

    # Create two memories with same base content (but unique due to UUIDs)
    base = "Machine learning works best with clean data preprocessing techniques"
    mem1_id = insert_memory(unique_content(base))
    mem2_id = insert_memory(unique_content(base))

    conn = get_db()

    # mem1: 3 confirmed predictions → boost 1.5^3 = 3.375, capped at 2.0
    for i in range(3):
        pred_id = predict(conn, f"Good pred {i}", mem1_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    # mem2: no predictions → boost 1.0

    conn.close()

    # Search for similar content
    results, _, _ = search_memories("machine learning data", mode="hybrid")

    # mem1 should rank higher due to reasoning boost
    result_ids = [r['id'] for r in results]

    # mem1 should appear in results (mem2 might not if search is tight)
    assert mem1_id in result_ids, "Memory with confirmed predictions should appear in search"

    # If mem2 also appears, mem1 should rank higher
    if mem2_id in result_ids:
        mem1_pos = result_ids.index(mem1_id)
        mem2_pos = result_ids.index(mem2_id)
        assert mem1_pos < mem2_pos, "Memory with confirmed predictions should rank higher"


def test_reasoning_boost_only_counts_resolved_predictions(test_db):
    """Only resolved predictions (confirmed/refuted) affect boost, not open ones."""
    mem_id = insert_memory(unique_content("Memory with mixed prediction statuses"))

    conn = get_db()

    # Create 2 confirmed, 1 refuted, 2 open predictions
    pred1_id = predict(conn, "Pred 1", mem_id, 0.8, None, "Expected 1")
    pred2_id = predict(conn, "Pred 2", mem_id, 0.8, None, "Expected 2")
    pred3_id = predict(conn, "Pred 3", mem_id, 0.8, None, "Expected 3")
    predict(conn, "Pred 4 (open)", mem_id, 0.8, None, "Expected 4")
    predict(conn, "Pred 5 (open)", mem_id, 0.8, None, "Expected 5")

    resolve_prediction_memory(conn, pred1_id, "Confirmed 1", confirmed=True)
    resolve_prediction_memory(conn, pred2_id, "Confirmed 2", confirmed=True)
    resolve_prediction_memory(conn, pred3_id, "Refuted", confirmed=False)

    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # boost = (1.5^2) / 1.5 = 1.5 (open predictions ignored)
    assert boost == pytest.approx(1.5, rel=0.01)


def test_reasoning_boost_memory_without_id_link(test_db):
    """Predictions not linked to a memory don't affect boost."""
    mem_id = insert_memory(unique_content("Memory that should not be affected"))

    conn = get_db()

    # Create prediction NOT linked to memory (memory_id=None)
    pred_id = predict(conn, "Unlinked prediction", None, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(mem_id)

    # Should still be 1.0 (no linked predictions)
    assert boost == 1.0


def test_reasoning_boost_via_relations_table(test_db):
    """Memory linked via memory_relations to a prediction memory gets boost."""
    from memory_tool.relations import relate_memories

    # Create base memory (the one we'll test)
    base_mem_id = insert_memory(unique_content("Base memory with reasoning"))

    # Create a prediction memory that references the base
    pred_mem_id = insert_memory(unique_content("Prediction based on base memory"))

    # Link them via relations table
    relate_memories(pred_mem_id, base_mem_id, "derived")

    conn = get_db()

    # Create confirmed prediction on the prediction memory
    pred_id = predict(conn, "Good prediction", pred_mem_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(base_mem_id)

    # Base memory should get boost because it's linked to a memory with confirmed prediction
    # boost = 1.3^1 = 1.3
    assert boost == pytest.approx(1.3, rel=0.01)


def test_reasoning_boost_via_derived_from_field(test_db):
    """Memory referenced in derived_from field gets boost."""
    # Create source memory
    source_mem_id = insert_memory(unique_content("Source memory for derivation"))

    # Create derived memory with derived_from field (JSON array)
    conn = get_db()
    derived_content = unique_content("Derived memory")
    derived_mem_id = conn.execute(
        "INSERT INTO memories (category, content, derived_from) VALUES (?, ?, ?)",
        ("learning", derived_content, f"[{source_mem_id}]")
    ).lastrowid
    conn.commit()

    # Create confirmed prediction on the derived memory
    pred_id = predict(conn, "Prediction from derived", derived_mem_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(source_mem_id)

    # Source memory should get boost because derived memory (which has confirmed prediction) cites it
    assert boost == pytest.approx(1.3, rel=0.01)


def test_reasoning_boost_via_citations_field(test_db):
    """Memory referenced in citations field gets boost."""
    # Create cited memory
    cited_mem_id = insert_memory(unique_content("Cited memory"))

    # Create citing memory with citations field (comma-separated)
    conn = get_db()
    citing_content = unique_content("Memory with citations")
    citing_mem_id = conn.execute(
        "INSERT INTO memories (category, content, citations) VALUES (?, ?, ?)",
        ("learning", citing_content, f"{cited_mem_id}, external-source")
    ).lastrowid
    conn.commit()

    # Create confirmed prediction on the citing memory
    pred_id = predict(conn, "Prediction from citing", citing_mem_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(cited_mem_id)

    # Cited memory should get boost
    assert boost == pytest.approx(1.3, rel=0.01)


def test_reasoning_boost_via_reasoning_field(test_db):
    """Memory referenced in reasoning field gets boost."""
    # Create reasoning memory
    reasoning_mem_id = insert_memory(unique_content("Reasoning chain memory"))

    # Create prediction memory with reasoning field
    conn = get_db()
    pred_content = unique_content("Prediction with reasoning chain")
    pred_mem_id = conn.execute(
        "INSERT INTO memories (category, content, reasoning) VALUES (?, ?, ?)",
        ("learning", pred_content, f"Based on memory {reasoning_mem_id}")
    ).lastrowid
    conn.commit()

    # Create confirmed prediction on this memory
    pred_id = predict(conn, "Prediction with reasoning", pred_mem_id, 0.8, None, "Expected")
    resolve_prediction_memory(conn, pred_id, "Confirmed", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(reasoning_mem_id)

    # Reasoning memory should get boost
    assert boost == pytest.approx(1.3, rel=0.01)


def test_reasoning_boost_multiple_confirmed_capped(test_db):
    """Multiple confirmed predictions get capped at REASONING_BOOST_CAP (1.8x)."""
    from memory_tool.config import REASONING_BOOST_CAP

    base_mem_id = insert_memory(unique_content("Memory with many confirmed predictions"))

    conn = get_db()

    # Create 5+ confirmed predictions to exceed cap
    # 1.3^5 = 3.71, but should be capped at 1.8
    for i in range(5):
        pred_id = predict(conn, f"Confirmed pred {i}", base_mem_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Confirmed {i}", confirmed=True)

    conn.close()

    boost = compute_reasoning_boost(base_mem_id)

    # Should be capped at REASONING_BOOST_CAP
    assert boost == pytest.approx(REASONING_BOOST_CAP, rel=0.01)


def test_reasoning_boost_refuted_predictions_penalty(test_db):
    """Refuted predictions reduce boost below 1.0."""
    base_mem_id = insert_memory(unique_content("Memory with refuted predictions"))

    conn = get_db()

    # Create 2 refuted predictions
    # 1.0 / 1.3 / 1.3 = ~0.59
    for i in range(2):
        pred_id = predict(conn, f"Refuted pred {i}", base_mem_id, 0.8, None, f"Expected {i}")
        resolve_prediction_memory(conn, pred_id, f"Refuted {i}", confirmed=False)

    conn.close()

    boost = compute_reasoning_boost(base_mem_id)

    # Should be less than 1.0
    expected_boost = 1.0 / (1.3 * 1.3)  # ~0.59
    assert boost == pytest.approx(expected_boost, rel=0.01)


def test_reasoning_boost_provenance_integration(test_db):
    """Verify all provenance fields work together to compute boost."""
    # Create a base memory that will be referenced
    base_mem_id = insert_memory(unique_content("Base knowledge memory"))

    conn = get_db()

    # Create memory 1: links via derived_from
    mem1_content = unique_content("Derived knowledge")
    mem1_id = conn.execute(
        "INSERT INTO memories (category, content, derived_from) VALUES (?, ?, ?)",
        ("learning", mem1_content, f"[{base_mem_id}]")
    ).lastrowid

    # Create memory 2: links via citations
    mem2_content = unique_content("Cited knowledge")
    mem2_id = conn.execute(
        "INSERT INTO memories (category, content, citations) VALUES (?, ?, ?)",
        ("learning", mem2_content, f"memory {base_mem_id}, other source")
    ).lastrowid

    # Create memory 3: links via reasoning
    mem3_content = unique_content("Reasoned knowledge")
    mem3_id = conn.execute(
        "INSERT INTO memories (category, content, reasoning) VALUES (?, ?, ?)",
        ("learning", mem3_content, f"Based on memory #{base_mem_id}")
    ).lastrowid

    conn.commit()

    # Create confirmed predictions on all three linking memories
    pred1_id = predict(conn, "Prediction 1", mem1_id, 0.9, None, "Expected 1")
    pred2_id = predict(conn, "Prediction 2", mem2_id, 0.9, None, "Expected 2")
    pred3_id = predict(conn, "Prediction 3", mem3_id, 0.9, None, "Expected 3")

    resolve_prediction_memory(conn, pred1_id, "Confirmed 1", confirmed=True)
    resolve_prediction_memory(conn, pred2_id, "Confirmed 2", confirmed=True)
    resolve_prediction_memory(conn, pred3_id, "Confirmed 3", confirmed=True)

    conn.close()

    # Base memory should get boost from all 3 confirmed predictions
    # boost = 1.3^3 = 2.197, capped at 1.8
    boost = compute_reasoning_boost(base_mem_id)
    from memory_tool.config import REASONING_BOOST_CAP
    assert boost == pytest.approx(REASONING_BOOST_CAP, rel=0.01)
