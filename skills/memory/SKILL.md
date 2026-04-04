---
name: memory
description: Persistent long-term memory system with beliefs, predictions, and knowledge graphs. Use for remembering decisions, learnings, and patterns across sessions.
---

# AI-IQ Memory System

Give your AI persistent memory that survives across sessions. Built on SQLite with hybrid search (keyword + semantic + graph).

## When to Use

Use AI-IQ memory when you need to:

- **Remember decisions**: "Why did we choose React over Vue?"
- **Track learnings**: "Redis needs network_mode: host for Docker"
- **Store preferences**: "User prefers dark mode"
- **Record errors**: "API timeout bug fixed by increasing connection pool"
- **Manage beliefs**: "TypeScript adoption will improve code quality (confidence: 0.8)"
- **Track predictions**: "New feature will reduce support tickets by 20%"

## Core Commands

All commands use the `memory-tool` CLI (installed with `pip install ai-iq`).

### Adding Memories

```bash
# Basic add
memory-tool add learning "Redis needs network_mode: host in Docker" --project MyApp

# With tags and priority
memory-tool add decision "Chose PostgreSQL over MongoDB" --tags database,architecture --priority 8

# With expiration (for TODOs)
memory-tool add pending "Review PR #123" --expires 2026-04-10

# With relationships
memory-tool add learning "Fixed CORS by adding credentials: true" --related 42 --project MyApp
```

**Categories**: `project`, `decision`, `preference`, `error`, `learning`, `pending`, `architecture`, `workflow`, `contact`

**Priority**: 0-10 (default: 5). Higher = more important.

### Searching Memories

```bash
# Hybrid search (keyword + semantic)
memory-tool search "docker networking"

# Semantic-only (vector similarity)
memory-tool search "docker networking" --semantic

# Keyword-only (FTS)
memory-tool search "docker networking" --keyword

# Verbose output
memory-tool search "docker networking" --full

# Get specific memory
memory-tool get 42
```

### Filtering & Listing

```bash
# List all for project
memory-tool list --project MyApp

# Filter by category
memory-tool list --category decision

# Show stale memories
memory-tool list --stale

# Show expired TODOs
memory-tool list --expired

# Show pending items
memory-tool pending
```

### Updating & Deleting

```bash
# Update content
memory-tool update 42 "Redis needs network_mode: host AND restart: always"

# Delete memory
memory-tool delete 42

# Merge duplicates
memory-tool merge 42 43  # Keep 43, mark 42 as superseded

# Mark as superseded
memory-tool supersede 42 43  # 42 is old, 43 is new
```

### Beliefs & Predictions

Track hypotheses and validate them over time.

```bash
# Create belief with confidence (0.0-1.0)
memory-tool believe "TypeScript will improve code quality" --confidence 0.8 --project MyApp

# Make prediction
memory-tool predict "New auth flow will reduce support tickets by 20%" --based-on 42 --confidence 0.7 --deadline 2026-05-01 --expect "Support tickets < 50/week"

# Resolve prediction
memory-tool resolve 15 --confirmed "Support tickets dropped to 35/week"
# OR
memory-tool resolve 15 --refuted "Support tickets stayed at 80/week"

# List beliefs
memory-tool beliefs              # All beliefs
memory-tool beliefs --weak       # Confidence < 0.5
memory-tool beliefs --strong     # Confidence > 0.8
memory-tool beliefs --conflicts  # Contradicting beliefs

# List predictions
memory-tool predictions --open       # Unresolved
memory-tool predictions --confirmed  # Proven true
memory-tool predictions --refuted    # Proven false
memory-tool predictions --expired    # Past deadline
```

### Knowledge Graph

Entities and relationships for context-aware retrieval.

```bash
# Add entities
memory-tool graph add project "MyApp" "E-commerce platform"
memory-tool graph add person "Alice" "Senior developer"
memory-tool graph add feature "AuthFlow" "OAuth2 authentication"

# Add relationships
memory-tool graph rel Alice works_on MyApp
memory-tool graph rel AuthFlow built_by Alice
memory-tool graph rel AuthFlow depends_on Redis

# Set facts
memory-tool graph fact MyApp language "TypeScript"
memory-tool graph fact MyApp status "production"

# Get entity with relationships
memory-tool graph get MyApp

# Find related entities (spreading activation)
memory-tool graph spread AuthFlow 2  # 2 hops

# Link memory to entity
memory-tool graph link 42 Redis

# Auto-link all memories to entities
memory-tool graph auto-link
```

### Focus (Context Loading)

Instantly load all context for a topic — memories, graph, pending items, beliefs, predictions.

```bash
# Quick context brief
memory-tool focus "whatsauction"

# Detailed view
memory-tool focus "docker" --full
```

Focus pulls together:
- Top matching memories (hybrid search)
- Knowledge graph entity + facts + relationships
- Last session snapshot mentioning the topic
- Active runs in progress for the topic
- Pending TODOs for the topic
- Beliefs and predictions
- Suggested next actions

Use this at the start of a session to get up to speed on any topic.

### Maintenance

```bash
# Smart suggestions (what needs attention)
memory-tool next

# Dream mode (consolidate duplicates, detect conflicts)
memory-tool dream

# Find potential duplicates
memory-tool conflicts

# Stale memories
memory-tool stale

# Hot memories (most accessed, immune to decay)
memory-tool hot

# Manual session snapshot
memory-tool snapshot "Added authentication, fixed CORS bug"

# Auto-detect changes and snapshot
memory-tool auto-snapshot

# Force decay (mark stale, expire old)
memory-tool decay

# Garbage collect old inactive memories
memory-tool gc 180  # Delete memories inactive for 180+ days

# Reindex for vector search
memory-tool reindex

# Backup
memory-tool backup

# Restore
memory-tool restore /root/backups/memory/memories_20260402.db

# Stats
memory-tool stats
```

## Python API

For programmatic access in Python agents:

```python
from ai_iq import Memory

memory = Memory()

# Add
memory.add("User prefers dark mode", category="preference", tags=["ui"])

# Search
results = memory.search("dark mode")
for r in results:
    print(f"#{r['id']}: {r['content']}")

# Update
memory.update(1, "User STRONGLY prefers dark mode")

# Delete
memory.delete(1)

# Beliefs
memory.believe("TypeScript improves quality", confidence=0.8)

# Predictions
memory.predict(
    prediction="Auth flow reduces tickets by 20%",
    based_on=[42],
    confidence=0.7,
    deadline="2026-05-01",
    expected_outcome="Tickets < 50/week"
)

# Knowledge graph
memory.graph_add_entity("project", "MyApp", "E-commerce platform")
memory.graph_relate("Alice", "works_on", "MyApp")
memory.graph_set_fact("MyApp", "language", "TypeScript")
```

See [PYTHON_API.md](https://github.com/kobie3717/ai-iq/blob/main/PYTHON_API.md) for complete API reference.

## Key Features

- **Single SQLite file** - No servers, no setup, fully portable
- **Hybrid search** - FTS5 keyword + sqlite-vec semantic + graph traversal
- **Memory decay** - FSRS-6 algorithm (like human memory)
- **Beliefs & predictions** - Track confidence, validate hypotheses
- **Knowledge graph** - Entities, relationships, spreading activation
- **Dream mode** - AI-powered consolidation (REM sleep for memory)
- **Auto-capture** - PostToolUse hook logs errors automatically
- **Framework-agnostic** - Works with any Python agent, not locked to Claude

## Installation

```bash
# Basic (keyword search only)
pip install ai-iq

# Full (with semantic search)
pip install ai-iq[full]
```

## Examples

See [examples/](https://github.com/kobie3717/ai-iq/tree/main/examples) for:
- Chatbot with memory
- Knowledge base builder
- Decision tracker
- Learning journal

## Differentiators vs claude-mem

- **Portable**: Single SQLite file, not tied to Claude Code
- **Beliefs & predictions**: Track confidence, validate over time
- **Knowledge graph**: Entities, relationships, spreading activation
- **Python API**: Use in any Python agent (`from ai_iq import Memory`)
- **Dream mode**: AI-powered consolidation and conflict detection
- **Framework-agnostic**: Works with Claude, OpenAI, local models, etc.

## Documentation

- [GitHub](https://github.com/kobie3717/ai-iq)
- [PyPI](https://pypi.org/project/ai-iq/)
- [Architecture](https://github.com/kobie3717/ai-iq/blob/main/ARCHITECTURE.md)
- [Python API](https://github.com/kobie3717/ai-iq/blob/main/PYTHON_API.md)
