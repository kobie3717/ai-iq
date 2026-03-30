# Contributing to AI-IQ

Thank you for your interest in contributing to AI-IQ! This document provides guidelines and information for contributors.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Good First Issues](#good-first-issues)
- [Architecture](#architecture)
- [Submitting Pull Requests](#submitting-pull-requests)
- [License](#license)

---

## Getting Started

AI-IQ is a biological memory system for AI agents. Before contributing, familiarize yourself with:

- **README.md** — Overview, features, quick start
- **ARCHITECTURE.md** — Technical deep-dive, biological memory principles, module reference
- **INSTALLATION.md** — Setup guide, Claude Code integration, hook configuration

**Key concepts**:
- Hybrid search (FTS5 + semantic + graph with RRF fusion)
- FSRS-6 spaced repetition algorithm for decay
- Graph intelligence (entities, relationships, spreading activation)
- Beliefs & predictions (Bayesian confidence updates)
- Dream mode (consolidation, reconsolidation, pruning)

---

## Development Setup

### Prerequisites

- **Python 3.10+** (3.8+ for base functionality, 3.10+ for all features)
- **SQLite 3.35+** (for FTS5 full-text search)
- **Optional**: `sqlite-vec`, `onnxruntime`, `tokenizers`, `numpy` (for semantic search)

### Installation

```bash
# Clone the repository
git clone https://github.com/kobie3717/ai-iq.git
cd ai-iq

# Install in development mode (editable)
pip install -e .

# Install with optional dependencies (semantic search)
pip install -e ".[full]"

# Install development dependencies (testing, type checking)
pip install -e ".[dev]"

# Verify installation
memory-tool --help
memory-tool stats
```

### Directory Structure

```
ai-iq/
├── memory_tool/           # Source code (25 Python modules)
│   ├── __init__.py
│   ├── cli.py             # Command-line interface
│   ├── core.py            # Central hub (re-exports all modules)
│   ├── config.py          # Paths, constants, logging
│   ├── database.py        # SQLite connection, schema init
│   ├── embedding.py       # Vector embeddings (all-MiniLM-L6-v2)
│   ├── memory_ops.py      # CRUD operations
│   ├── graph.py           # Knowledge graph
│   ├── beliefs.py         # Belief tracking (basic)
│   ├── beliefs_extended.py # Bayesian belief system
│   ├── dream.py           # Consolidation, reconsolidation
│   ├── fsrs.py            # FSRS-6 spaced repetition
│   ├── identity.py        # Self-model, trait discovery
│   ├── meta_learning.py   # Search tuning
│   ├── narrative.py       # Causal story construction
│   └── ...                # (15 more modules)
├── tests/                 # Test suite (24 files, 268 tests)
├── hooks/                 # Claude Code integration hooks
├── pyproject.toml         # Project metadata, dependencies
├── README.md              # User-facing documentation
├── ARCHITECTURE.md        # Technical deep-dive
├── INSTALLATION.md        # Setup guide
├── CONTRIBUTING.md        # This file
└── LICENSE                # MIT License
```

---

## Code Style

### General Guidelines

- **Follow PEP 8** — Use 4 spaces for indentation, max 120 chars per line
- **Type hints on all functions** — Helps with IDE autocomplete and mypy
- **Docstrings on all public functions** — Brief one-liner or detailed multi-line
- **Logging instead of print()** — Use `config.get_logger(__name__)`, never `print()`
- **No bare `except:`** — Always catch specific exceptions
- **Functional where possible** — Pure functions with no side effects (see `fsrs.py`, `utils.py`)

### Type Hints Example

```python
from typing import Optional, List, Dict, Tuple, Any

def add_memory(
    content: str,
    category: str,
    project: Optional[str] = None,
    tags: str = "",
    priority: int = 0
) -> int:
    """Add a new memory to the database.

    Args:
        content: Memory content (plain text)
        category: One of: project, decision, preference, error, learning, pending
        project: Optional project name
        tags: Comma-separated tags
        priority: Priority level (0-10)

    Returns:
        Memory ID (int)
    """
    # Implementation...
    return memory_id
```

### Logging Example

```python
from .config import get_logger

logger = get_logger(__name__)

def process_data(data: List[str]) -> None:
    logger.debug(f"Processing {len(data)} items")
    try:
        # Process data...
        logger.info("Processing completed successfully")
    except ValueError as e:
        logger.error(f"Invalid data: {e}")
        raise
```

### Testing Example

```python
import pytest
from memory_tool.fsrs import fsrs_retention, fsrs_new_stability

def test_fsrs_retention():
    """Test FSRS retention curve calculation."""
    # Zero stability = zero retention
    assert fsrs_retention(0, 10) == 0.0

    # High stability = high retention
    retention = fsrs_retention(100, 10)
    assert 0.8 < retention < 1.0

    # Retention decreases over time
    r1 = fsrs_retention(50, 10)
    r2 = fsrs_retention(50, 50)
    assert r1 > r2

def test_fsrs_new_stability():
    """Test stability update after review."""
    new_s = fsrs_new_stability(old_s=50, old_d=5, rating=3, elapsed_days=10)
    assert new_s > 50  # Stability should increase with good rating
```

---

## Making Changes

### Workflow

1. **Fork the repository** on GitHub
2. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Write tests first** (test-driven development)
   - Add tests in `tests/` directory
   - Run `python -m pytest` to verify tests fail (red)
4. **Implement the feature**
   - Make changes to `memory_tool/` modules
   - Follow code style guidelines
   - Add type hints and docstrings
5. **Run tests again** to verify they pass (green)
   ```bash
   python -m pytest
   ```
6. **Run type checker** (optional but recommended)
   ```bash
   python -m mypy memory_tool/
   ```
7. **Commit your changes**
   ```bash
   git add tests/ memory_tool/
   git commit -m "Add feature: your feature description"
   ```
8. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```
9. **Submit a pull request** on GitHub

### Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues if applicable ("Fixes #123")

**Examples**:
```
Add Obsidian vault import functionality

Implement parser for Obsidian markdown files with frontmatter.
Detects project/tags from frontmatter, converts to memories.

Fixes #42
```

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_fsrs.py

# Run tests matching pattern
python -m pytest -k "test_fsrs"

# Run with coverage report
python -m pytest --cov=memory_tool --cov-report=html

# Run in verbose mode
python -m pytest -v
```

### Test Structure

Tests are organized to mirror the source code structure:

```
tests/
├── test_cli.py              # CLI command tests
├── test_memory_ops.py       # CRUD operation tests
├── test_embedding.py        # Vector embedding tests
├── test_graph.py            # Knowledge graph tests
├── test_beliefs.py          # Belief system tests
├── test_dream.py            # Dream mode tests
├── test_fsrs.py             # FSRS algorithm tests
├── test_identity.py         # Identity layer tests
└── ...
```

### Test Database

All tests use in-memory SQLite databases (`:memory:`) to avoid file I/O and ensure test isolation:

```python
import sqlite3
from memory_tool.database import init_db

def test_example():
    """Test with in-memory database."""
    conn = sqlite3.connect(':memory:')
    init_db(conn)

    # Test operations...

    conn.close()
```

### Test Coverage

Current coverage (as of v5.0.0):
- **Core modules** (fsrs, importance, utils, config): 100%
- **Memory operations**: 95%
- **Graph intelligence**: 90%
- **Belief system**: 85%
- **Overall**: ~90%

**Goal**: Maintain >85% coverage. New features should include tests.

---

## Good First Issues

These are great starting points for new contributors:

### 1. Add More Trait Patterns (Easy)

**File**: `memory_tool/identity.py`

The identity layer discovers behavioral patterns from memories. Add more regex patterns to `TRAIT_PATTERNS`:

```python
TRAIT_PATTERNS = {
    "forgets_null_checks": [
        r"forgot to check (if|whether) .* (is|was) null",
        r"null(pointer)? (exception|error)",
        # Add more patterns here
    ],
    # Add new traits here
}
```

**Ideas**:
- "prefers_tabs_over_spaces" — detects indentation preferences
- "forgets_error_handling" — detects missing try/catch
- "optimizes_prematurely" — detects premature optimization patterns

**Test**: Add tests in `tests/test_identity.py`

---

### 2. Improve Narrative Text Generation (Medium)

**File**: `memory_tool/narrative.py`

The narrative module constructs cause-effect stories but generates basic text. Make it more natural:

```python
# Current:
"Error X LEADS_TO Investigation Y RESOLVES Bug Z"

# Better:
"Error X prompted Investigation Y, which ultimately resolved Bug Z."
```

**Requirements**:
- Template-based generation with variety
- Handle different causal edge types (PREVENTS, REQUIRES, etc.)
- Include entity types in narrative (person vs project vs feature)

**Test**: Add tests in `tests/test_narrative.py`

---

### 3. Add CSV Export (Medium)

**File**: `memory_tool/export.py`

Add a `--format csv` option to export command:

```bash
memory-tool export --format csv --output memories.csv
```

**Requirements**:
- Export all active memories to CSV
- Columns: id, category, content, project, tags, created_at, updated_at, priority, access_count
- Handle commas and quotes in content (proper CSV escaping)
- Include header row

**Test**: Add tests in `tests/test_export.py`

---

### 4. Add Obsidian Vault Import (Hard)

**File**: `memory_tool/sync.py` (or new `obsidian.py` module)

Import Obsidian markdown notes as memories:

```bash
memory-tool import-obsidian /path/to/vault/
```

**Requirements**:
- Parse markdown files with YAML frontmatter
- Extract project/tags from frontmatter
- Use filename as topic_key (for upserts)
- Detect wiki-style links `[[Entity Name]]` and create graph entities
- Skip duplicates (use content hash)

**Test**: Add tests with sample Obsidian vault structure

---

### 5. Improve the Comparison Table (Easy)

**File**: `README.md`

The comparison table in README compares AI-IQ to alternatives. Improve it:

- Add more alternatives (Mem0, Zep, LangChain Memory)
- Add more comparison dimensions (privacy, cost, latency, ease of setup)
- Add links to each alternative
- Consider making it a separate `COMPARISON.md` file if it gets large

**No code changes needed** — documentation only.

---

### 6. Add More Test Cases for Edge Cases (Easy-Medium)

Pick any module and add tests for edge cases:

**Examples**:
- Empty strings in `utils.auto_tag()`
- Very long content (>100KB) in `memory_ops.add_memory()`
- Unicode/emoji in memory content
- Concurrent access (multiple threads)
- Invalid dates in `dream.normalize_dates()`
- Circular relationships in `graph.spreading_activation()`

**Test files**: Any file in `tests/`

---

## Architecture

Before making changes, read [ARCHITECTURE.md](ARCHITECTURE.md) to understand:

- **Biological memory principles** — How AI-IQ maps to brain functions
- **Module reference** — What each of the 25 modules does
- **Data flow** — How operations move through the system
- **Schema** — Database tables and relationships
- **Design decisions** — Why we chose SQLite, FSRS, hybrid search, etc.

**Key principles**:
1. **Progressive disclosure** — Show minimal info by default, `--full` for details
2. **Zero dependencies** — Core functionality works with Python stdlib only
3. **Privacy-first** — All data local, no cloud services, no API keys
4. **Self-learning** — System improves over time via meta-learning
5. **Biological inspiration** — Memory system models human cognition

---

## Submitting Pull Requests

### Before Submitting

- [ ] All tests pass (`python -m pytest`)
- [ ] Code follows style guidelines (PEP 8, type hints, docstrings)
- [ ] New features include tests
- [ ] No bare `except:` clauses
- [ ] Logging used instead of `print()`
- [ ] Documentation updated if needed (README, ARCHITECTURE, docstrings)

### PR Description Template

```markdown
## Summary
Brief description of what this PR does.

## Motivation
Why is this change needed? What problem does it solve?

## Changes
- List of changes
- Made in this PR

## Testing
How was this tested? What test cases were added?

## Screenshots (if applicable)
Before/after screenshots for UI changes or output format changes.

## Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)

Fixes #123 (if applicable)
```

### Review Process

1. Maintainer will review within 1-3 days
2. May request changes or ask questions
3. Once approved, maintainer will merge
4. Thank you for your contribution!

---

## License

By contributing to AI-IQ, you agree that your contributions will be licensed under the MIT License.

See [LICENSE](LICENSE) for details.

---

## Questions?

- **GitHub Issues**: https://github.com/kobie3717/ai-iq/issues
- **GitHub Discussions**: https://github.com/kobie3717/ai-iq/discussions
- **Discord**: https://discord.gg/Y2jCXNGgE

Thank you for contributing to AI-IQ!
