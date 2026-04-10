# AI-IQ

Give your AI long-term memory in 1 command.

LLMs forget everything. AI-IQ makes them remember.

> **Part of the Claw Stack:** AI-IQ is the substrate of a larger pipeline —
> **Memory → Evaluation → Credential → Access Control**. Agents earn W3C Verifiable Credentials
> through proof-of-work, then present them to gain scoped access to other agents' memory via
> [`bot-circus`](https://github.com/kobie3717/bot-circus). Runs standalone or as part of the full stack.
>
> Install both as Claude Code plugins:
> ```
> /plugin marketplace add kobie3717/ai-iq
> /plugin marketplace add kobie3717/bot-circus
> ```

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

## Claude Code Plugin

Use AI-IQ directly in Claude Code with auto-capture:

```bash
/plugin marketplace add kobie3717/ai-iq
/plugin install ai-iq
```

See [CLAUDE_CODE_PLUGIN.md](CLAUDE_CODE_PLUGIN.md) for details.

## Why AI-IQ?

- **Single SQLite file = your AI's brain** — No servers, no vector DB, no setup
- **No cloud dependencies** — Works offline, owns your data, zero API keys
- **Works with any Python agent** — Not locked to Claude, OpenAI, or any vendor
- **Hybrid search** — Keyword (FTS5) + semantic (vector) + graph traversal
- **Memories decay naturally** — FSRS-6 algorithm like human memory

## Advanced Features

See [docs/REFERENCE.md](docs/REFERENCE.md) for complete documentation:

- **Passport System** — Complete identity card for any memory (graph connections, provenance chain, access patterns, confidence score)
- **Reflexion Self-Improvement** — Learn from mistakes with structured reflections (20-40% task improvement)
- **Beliefs & Predictions** — Confidence tracking with Bayesian updates
- **Knowledge Graph** — Entities, relationships, spreading activation
- **Dream Mode** — REM-like consolidation (dedup, conflict detection)
- **Identity Layer** — Auto-discovers behavioral traits
- **Narrative Memory** — Builds cause-effect stories from causal graph
- **Meta-Learning** — Search improves from feedback loops

### Passport System

Every memory has a "passport" — its complete identity card across all dimensions:

```bash
memory-tool passport 42
```

Shows:
- **Core identity**: content, category, project, tags
- **Graph connections**: linked entities with their relationships
- **Memory relationships**: derived-from, related, supersedes chains
- **Provenance**: citations, reasoning, source memories
- **Usage stats**: access count, revisions, FSRS state
- **Passport score**: composite 0-10 score from priority, access patterns, proof count, graph connections, and recency
- **Spreading activation**: related entities discovered via graph traversal

Like a traveler's passport proves who you are and where you've been, a memory passport is its complete dossier.

### Reflexion Self-Improvement

Learn from past mistakes with structured reflections (20-40% improvement on repeated tasks):

```bash
# Before starting a task
memory-tool reflect-load "nginx configuration"
# Shows: what failed before, what worked, what to do differently

# After completing a task
memory-tool reflect "Fixed nginx SSL config" \
  --outcome success \
  --worked "Tested syntax with nginx -t first" \
  --failed "None" \
  --next "Keep testing syntax before reload"

# Review patterns
memory-tool lessons
# Shows: task types with high failure rates needing attention
```

See [docs/REFLEXION.md](docs/REFLEXION.md) for complete guide.

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
