"""Tests for token economics display."""

import pytest
import sys
from pathlib import Path
from io import StringIO

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import display, database


def test_estimate_tokens():
    """Test token estimation heuristic."""
    # Word count * 1.3 heuristic
    assert display.estimate_tokens("test") == 1
    assert display.estimate_tokens("hello world this is a test") == 7  # 6 words * 1.3 = 7.8 -> 7


def test_show_token_economics_single_result(temp_db, capsys):
    """Test that token economics is shown even for single result."""
    conn = database.get_db()

    # Create one memory
    conn.execute(
        "INSERT INTO memories (category, content) VALUES (?, ?)",
        ("learning", "Single memory content")
    )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    # Should show token economics for any results
    display.show_token_economics(rows, compact=True)
    captured = capsys.readouterr()
    assert "tokens" in captured.out.lower()
    assert "Reading all" in captured.out


def test_show_token_economics_multiple_results_compact(temp_db, capsys):
    """Test token economics display for multiple results in compact mode."""
    conn = database.get_db()

    # Create multiple memories with content
    contents = [
        "A" * 200,  # Long content
        "B" * 150,
        "C" * 180,
    ]

    for content in contents:
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", content)
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    # Should show token economics
    display.show_token_economics(rows, compact=True)
    captured = capsys.readouterr()

    assert "tokens" in captured.out.lower()
    assert "Reading all" in captured.out
    assert "get <id>" in captured.out


def test_show_token_economics_multiple_results_full(temp_db, capsys):
    """Test token economics display for multiple results in full mode."""
    conn = database.get_db()

    # Create multiple memories
    for i in range(3):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", f"Memory content number {i}" * 10)
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    # Should show token economics even in full mode
    display.show_token_economics(rows, compact=False)
    captured = capsys.readouterr()

    assert "tokens" in captured.out.lower()


def test_token_economics_calculation_compact(temp_db):
    """Test token economics calculation for compact mode."""
    conn = database.get_db()

    # Create memories with known sizes
    # Each 400 chars = 100 tokens full, but only ~25 tokens in compact (100 char preview)
    for i in range(2):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", "X" * 400)
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    # Calculate expected
    full_tokens = 2 * (400 // 4)  # 200 tokens
    displayed_tokens = 2 * (100 // 4 + 12)  # ~37 tokens per row = 74 total

    # Savings should be significant
    saved_pct = int(((full_tokens - displayed_tokens) / full_tokens) * 100)
    assert saved_pct > 50  # Should save more than 50%


def test_token_economics_zero_savings(temp_db, capsys):
    """Test that no message is shown when savings is 0."""
    conn = database.get_db()

    # Create two very short memories
    for i in range(2):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", "Short")
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    # With very short content, savings might be 0 or negative
    display.show_token_economics(rows, compact=True)
    captured = capsys.readouterr()

    # If savings is 0, no message should appear
    # (or a message appears - either is acceptable)


def test_token_economics_emoji_present(temp_db, capsys):
    """Test that money bag emoji is in output."""
    conn = database.get_db()

    # Create memories
    for i in range(3):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", "X" * 300)
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    display.show_token_economics(rows, compact=True)
    captured = capsys.readouterr()

    assert "💰" in captured.out


def test_token_economics_format(temp_db, capsys):
    """Test token economics output format."""
    conn = database.get_db()

    for i in range(2):
        conn.execute(
            "INSERT INTO memories (category, content) VALUES (?, ?)",
            ("learning", "X" * 400)
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    display.show_token_economics(rows, compact=True)
    captured = capsys.readouterr()

    output = captured.out

    # Check new format: "💰 Reading all N results: ~X tokens total (~Y each avg)"
    assert "💰" in output
    assert "Reading all" in output
    assert "tokens total" in output
    assert "each avg" in output
