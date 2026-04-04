# AI-IQ Plugin

This plugin provides persistent long-term memory for Claude Code sessions.

## Memory Commands

Use `memory-tool` for all memory operations:

```bash
# Add memories
memory-tool add learning "Redis needs network_mode: host" --project MyApp

# Search
memory-tool search "docker networking"

# Beliefs & predictions
memory-tool believe "TypeScript improves quality" --confidence 0.8
memory-tool predict "Auth flow reduces tickets 20%" --deadline 2026-05-01

# Focus (context loading)
memory-tool focus "project-name"       # Instant context brief
memory-tool focus "topic" --full       # Detailed view

# Maintenance
memory-tool next    # Smart suggestions
memory-tool dream   # AI consolidation
memory-tool stats   # Show statistics
```

## Auto-Capture

The plugin automatically:
- Captures failed Bash commands as error memories (PostToolUse hook)
- Generates session snapshots on Stop
- Logs tool usage patterns

## Skills

See `/skills/memory/SKILL.md` for complete documentation on:
- Memory categories and priorities
- Search strategies
- Knowledge graph usage
- Belief and prediction tracking
- Memory maintenance

## Python API

For programmatic access:

```python
from ai_iq import Memory

memory = Memory()
memory.add("User prefers dark mode", category="preference")
results = memory.search("dark mode")
```

## Storage

Memories are stored in `~/.ai-iq/memories.db` (single SQLite file).

## Documentation

- Main repo: https://github.com/kobie3717/ai-iq
- PyPI: https://pypi.org/project/ai-iq/
- Skills: See `/skills/memory/SKILL.md`
