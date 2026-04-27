"""Tests for embedding sanitization and normalization."""

import math
import pytest
from memory_tool.embedding import sanitize_and_normalize_embedding


def test_all_zero_vector():
    """All-zero vector returns all-zero (no NaN from divide by zero)."""
    vec = [0.0, 0.0, 0.0, 0.0]
    result = sanitize_and_normalize_embedding(vec)
    assert result == [0.0, 0.0, 0.0, 0.0]
    assert not any(math.isnan(v) for v in result)


def test_vector_with_nan():
    """Vector with NaN entry gets 0.0 in that slot, rest normalized."""
    vec = [1.0, float('nan'), 2.0, 1.0]
    result = sanitize_and_normalize_embedding(vec)

    # Second element should be 0
    assert result[1] == 0.0

    # No NaN in output
    assert not any(math.isnan(v) for v in result)

    # Should be normalized (magnitude ~1.0)
    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6


def test_vector_with_positive_inf():
    """Vector with +Inf gets 0.0 in that slot."""
    vec = [1.0, float('inf'), 2.0]
    result = sanitize_and_normalize_embedding(vec)

    assert result[1] == 0.0
    assert not any(math.isinf(v) for v in result)

    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6


def test_vector_with_negative_inf():
    """Vector with -Inf gets 0.0 in that slot."""
    vec = [1.0, float('-inf'), 2.0]
    result = sanitize_and_normalize_embedding(vec)

    assert result[1] == 0.0
    assert not any(math.isinf(v) for v in result)

    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6


def test_already_unit_vector():
    """Already-unit vector returns essentially same vector."""
    # Create unit vector
    vec = [0.6, 0.8, 0.0]  # magnitude = 1.0
    result = sanitize_and_normalize_embedding(vec)

    # Should be very close to original
    for i, v in enumerate(vec):
        assert abs(result[i] - v) < 1e-9


def test_long_random_vector():
    """Long random vector outputs magnitude ≈ 1.0."""
    import random
    random.seed(42)

    vec = [random.uniform(-10, 10) for _ in range(100)]
    result = sanitize_and_normalize_embedding(vec)

    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6

    # No NaN or Inf
    assert not any(math.isnan(v) or math.isinf(v) for v in result)


def test_empty_vector():
    """Empty vector returns empty, no crash."""
    vec = []
    result = sanitize_and_normalize_embedding(vec)
    assert result == []


def test_none_entries():
    """None entries are handled (treated as 0.0)."""
    vec = [1.0, None, 2.0, None]
    result = sanitize_and_normalize_embedding(vec)

    assert result[1] == 0.0
    assert result[3] == 0.0

    # Should be normalized
    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6


def test_mixed_corruption():
    """Vector with NaN, Inf, None, and normal values."""
    vec = [1.0, float('nan'), 2.0, float('inf'), None, 3.0, float('-inf')]
    result = sanitize_and_normalize_embedding(vec)

    # Corrupted entries should be 0
    assert result[1] == 0.0  # NaN
    assert result[3] == 0.0  # +Inf
    assert result[4] == 0.0  # None
    assert result[6] == 0.0  # -Inf

    # Clean entries should be non-zero
    assert result[0] != 0.0
    assert result[2] != 0.0
    assert result[5] != 0.0

    # Should be normalized
    magnitude = math.sqrt(sum(v * v for v in result))
    assert abs(magnitude - 1.0) < 1e-6

    # No corruption in output
    assert not any(v is None or math.isnan(v) or math.isinf(v) for v in result)
