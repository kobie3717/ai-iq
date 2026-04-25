#!/usr/bin/env python3
"""Quick test of the three new upgrades."""

import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ppr():
    """Test Personalized PageRank module."""
    print("Testing PPR...")
    from memory_tool.ppr import personalized_pagerank, ppr_boost_search_results

    # Test with empty seeds
    result = personalized_pagerank("", [], top_k=5)
    assert result == [], "Empty seeds should return empty list"

    # Test boost with empty results
    result = ppr_boost_search_results([])
    assert result == [], "Empty results should return empty list"

    print("✓ PPR module works")

def test_procedures():
    """Test Procedural Memory module."""
    print("Testing Procedures...")
    from memory_tool.procedures import (
        add_procedure, get_procedure, list_procedures,
        procedure_succeed, procedure_fail, procedure_stats
    )

    # Test add procedure
    success = add_procedure("test_proc", ["step1", "step2"], project="test")
    assert success, "Should create procedure"

    # Test get procedure
    proc = get_procedure("test_proc")
    assert proc is not None, "Should retrieve procedure"
    assert len(proc['steps']) == 2, "Should have 2 steps"

    # Test succeed
    success = procedure_succeed("test_proc")
    assert success, "Should mark success"

    # Test fail
    success = procedure_fail("test_proc", "test failure")
    assert success, "Should mark failure"

    # Test stats
    stats = procedure_stats()
    assert stats['total_procedures'] >= 1, "Should have at least 1 procedure"

    # Clean up
    from memory_tool.procedures import delete_procedure
    delete_procedure("test_proc")

    print("✓ Procedures module works")

def test_context_budget():
    """Test Context Window Budgeting module."""
    print("Testing Context Budget...")
    from memory_tool.context_budget import (
        estimate_tokens, memory_to_text, retrieve_with_budget,
        format_memories_for_context, budget_stats
    )

    # Test token estimation
    tokens = estimate_tokens("Hello world")
    assert tokens > 0, "Should estimate tokens"

    # Test memory to text
    mem = {'content': 'test', 'category': 'learning', 'project': 'test'}
    text = memory_to_text(mem)
    assert 'test' in text, "Should include content"

    # Test budget stats
    stats = budget_stats()
    assert 'total_memories' in stats, "Should return stats"

    print("✓ Context Budget module works")

if __name__ == "__main__":
    try:
        test_ppr()
        test_procedures()
        test_context_budget()
        print("\n✓ All upgrade tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
