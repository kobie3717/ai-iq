# AI-IQ

Give your AI long-term memory in 1 command.

LLMs forget everything. AI-IQ makes them remember.

## Install

```bash
pip install ai-iq
```

## Quick Start

```python
from ai_iq import Memory

memory = Memory()

# Add memories
memory.add("User prefers dark mode", tags=["preference", "ui"])
memory.add("Redis bug fixed with network_mode: host", category="learning")

# Search (hybrid keyword + semantic)
results = memory.search("redis networking")
for r in results:
    print(f"#{r['id']}: {r['content']}")

# Update and delete
memory.update(1, "User STRONGLY prefers dark mode")
memory.delete(1)
```

## CLI

```bash
memory-tool add learning "Docker needs network_mode: host" --project MyApp
memory-tool search "docker networking"
memory-tool dream  # Consolidate duplicates, detect conflicts
```

## Why AI-IQ?

- **Single SQLite file = your AI's brain** — No servers, no vector DB, no setup
- **No cloud dependencies** — Works offline, owns your data, zero API keys
- **Works with any Python agent** — Not locked to Claude, OpenAI, or any vendor
- **Hybrid search** — Keyword (FTS5) + semantic (vector) + graph traversal
- **Memories decay naturally** — FSRS-6 algorithm like human memory

## Advanced Features

See [docs/REFERENCE.md](docs/REFERENCE.md) for complete documentation:

- **Beliefs & Predictions** — Confidence tracking with Bayesian updates
- **Knowledge Graph** — Entities, relationships, spreading activation
- **Dream Mode** — REM-like consolidation (dedup, conflict detection)
- **Identity Layer** — Auto-discovers behavioral traits
- **Narrative Memory** — Builds cause-effect stories from causal graph
- **Meta-Learning** — Search improves from feedback loops

## Example

See [examples/chatbot_with_memory.py](examples/chatbot_with_memory.py)

## Documentation

[Complete Reference](docs/REFERENCE.md) • [Examples](examples/) • [Architecture](ARCHITECTURE.md)

## Requirements

Python 3.8+ and SQLite 3.37+. Optional: `pip install ai-iq[full]` for semantic search.

## License

MIT

## Links

- **GitHub**: [github.com/kobie3717/ai-iq](https://github.com/kobie3717/ai-iq)
- **PyPI**: [pypi.org/project/ai-iq](https://pypi.org/project/ai-iq/)
- **Discord**: [discord.gg/Y2jCXNGgE](https://discord.gg/Y2jCXNGgE)
