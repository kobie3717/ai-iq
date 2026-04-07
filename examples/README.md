# AI-IQ Examples

This directory contains example scripts demonstrating how to use the AI-IQ Python API.

## Examples

### basic_usage.py
The simplest possible example - add, search, update, delete memories.

```bash
python examples/basic_usage.py
```

### api_demo.py
Complete API demonstration showing all major operations:
- Creating memory instances
- Adding memories with various options
- Searching with hybrid mode
- Getting specific memories
- Updating and deleting
- Listing with filters
- Statistics

```bash
python examples/api_demo.py
```

### chatbot_with_memory.py
Interactive chatbot that remembers what you tell it and recalls related context.

```bash
python examples/chatbot_with_memory.py
```

Try saying:
- "I love pizza"
- "Italian food is great"
- "What do I like?"

The bot will search its memories and show you related things it remembers.

## Running Examples

All examples can be run from the repository root:

```bash
cd /path/to/ai-iq
python examples/basic_usage.py
python examples/api_demo.py
python examples/chatbot_with_memory.py
```

Each example creates its own database file:
- `basic_usage.py` uses `./memories.db` (default)
- `api_demo.py` uses `./demo.db`
- `chatbot_with_memory.py` uses `./chatbot_memory.db`

## Learning Path

1. Start with `basic_usage.py` to understand the core API
2. Run `api_demo.py` to see all features
3. Try `chatbot_with_memory.py` for an interactive experience
4. Read [docs/REFERENCE.md](../docs/REFERENCE.md) for advanced features

## Building Your Own

The Memory API is simple:

```python
from ai_iq import Memory

memory = Memory()  # or Memory("custom.db")

# Add
mem_id = memory.add("content", tags=["tag1"], category="learning")

# Search
results = memory.search("query")

# Update
memory.update(mem_id, "new content")

# Delete
memory.delete(mem_id)

# List
all_learning = memory.list(category="learning")

# Stats
stats = memory.stats()
```

See [docs/REFERENCE.md](../docs/REFERENCE.md) for complete API documentation.
