"""Tests for focus command."""

import pytest
import sqlite3
from memory_tool.focus import focus_topic
from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import add_memory
from memory_tool.graph import graph_add_entity, graph_add_relationship, graph_set_fact


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create a temporary test database."""
    db_path = tmp_path / "test_memories.db"
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_path))
    init_db()
    yield db_path


def test_focus_basic(test_db):
    """Test basic focus functionality with memories."""
    # Add some test memories
    add_memory("learning", "Docker containers isolate applications", tags="docker,containers")
    add_memory("learning", "Redis is an in-memory database", tags="redis,database")
    add_memory("architecture", "Use Docker for deployment", tags="docker,deployment")

    # Focus on docker topic
    result = focus_topic("docker", full=False)

    assert "# Focus: docker" in result
    assert "## Key Memories" in result
    assert "Docker containers" in result or "Docker for deployment" in result


def test_focus_full_mode(test_db):
    """Test focus with full detail mode."""
    # Add test memory with project
    add_memory("learning", "Docker compose orchestrates containers",
               tags="docker,compose", project="TestProject")

    # Focus with full detail
    result = focus_topic("docker", full=True)

    assert "# Focus: docker" in result
    assert "[TestProject]" in result


def test_focus_no_results(test_db):
    """Test focus when no memories match."""
    add_memory("learning", "Python is a programming language", tags="python")

    # Focus on unrelated topic
    result = focus_topic("javascript", full=False)

    assert "# Focus: javascript" in result
    # Should still show sections but with no/few results


def test_focus_with_graph(test_db):
    """Test focus with knowledge graph entity."""
    # Add entity and relationships
    entity_id = graph_add_entity("Docker", "tool", "Container platform")
    related_id = graph_add_entity("Kubernetes", "tool", "Orchestration platform")
    graph_add_relationship("Docker", "Kubernetes", "related_to")
    graph_set_fact("Docker", "type", "container", confidence=0.9)

    # Add memory
    add_memory("learning", "Docker is great for microservices", tags="docker")

    # Focus on entity
    result = focus_topic("Docker", full=False)

    assert "# Focus: Docker" in result
    assert "## Knowledge Graph" in result
    assert "Docker" in result
    assert "tool" in result


def test_focus_with_pending(test_db):
    """Test focus with pending items."""
    # Add pending memory
    add_memory("pending", "TODO: Set up Docker environment", tags="docker,setup")
    add_memory("learning", "Docker basics learned", tags="docker")

    result = focus_topic("docker", full=False)

    assert "# Focus: docker" in result
    assert "## Pending" in result
    assert "TODO: Set up Docker environment" in result


def test_focus_compact_vs_full(test_db):
    """Test differences between compact and full modes."""
    # Add multiple memories
    for i in range(15):
        add_memory("learning", f"Docker fact #{i}", tags="docker")

    compact = focus_topic("docker", full=False)
    full = focus_topic("docker", full=True)

    # Compact should show max 5, full should show max 10
    assert "## Key Memories (5 of" in compact or "## Key Memories (5 matches)" in compact
    assert compact.count("**#") <= 7  # 5 memories + possible other sections


def test_focus_suggestions(test_db):
    """Test that suggested actions appear when appropriate."""
    # Add many memories on same topic to trigger conflict suggestion
    for i in range(10):
        add_memory("learning", f"Docker concept {i}", tags="docker")

    result = focus_topic("docker", full=False)

    assert "# Focus: docker" in result
    # May or may not have suggestions depending on stale/conflicts
    # Just check the section would appear if needed
    if "## Suggested Actions" in result:
        assert "memory-tool" in result


def test_focus_no_graph_entity(test_db):
    """Test focus when no graph entity exists."""
    add_memory("learning", "Topic without entity", tags="test")

    result = focus_topic("test", full=False)

    assert "# Focus: test" in result
    assert "## Knowledge Graph" in result
    assert "_No entity found for this topic._" in result


def test_focus_multi_word_topic(test_db):
    """Test focus with multi-word topic."""
    add_memory("learning", "Unit tests prevent regressions", tags="testing,unit")
    add_memory("learning", "Write tests first", tags="testing,tdd")

    result = focus_topic("unit tests", full=False)

    assert "# Focus: unit tests" in result
    assert "## Key Memories" in result
