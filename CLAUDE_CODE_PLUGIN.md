# AI-IQ Claude Code Plugin

Use AI-IQ as a Claude Code plugin for automatic memory capture and session persistence.

## Installation

### Quick Install (Recommended)

```bash
/plugin marketplace add kobie3717/ai-iq
/plugin install ai-iq
```

### Manual Install

```bash
# Clone to plugins directory
cd ~/.claude/plugins/marketplaces
git clone https://github.com/kobie3717/ai-iq kobie3717/ai-iq

# Install Python package
pip install ai-iq

# Restart Claude Code
```

## What You Get

Once installed, the plugin:

1. **Auto-captures errors** - Failed Bash commands saved to memory
2. **Session snapshots** - Auto-generates summaries on Stop
3. **Memory skills** - Claude knows how to use memory-tool
4. **Seamless integration** - No manual setup needed

## Usage

### Memory Commands

```bash
# Add memories
memory-tool add learning "Redis needs network_mode: host" --project MyApp
memory-tool add decision "Chose PostgreSQL" --priority 8

# Search
memory-tool search "redis networking"
memory-tool get 42  # Get specific memory

# Beliefs & predictions
memory-tool believe "TypeScript improves quality" --confidence 0.8
memory-tool predict "Auth flow reduces tickets 20%" --deadline 2026-05-01

# Smart maintenance
memory-tool next    # What needs attention?
memory-tool dream   # AI consolidation
memory-tool stats   # Show statistics
```

### Python API

```python
from ai_iq import Memory

memory = Memory()
memory.add("User prefers dark mode", tags=["ui", "preference"])
results = memory.search("dark mode")
```

## Features

- **Single SQLite file** - No servers, fully portable
- **Hybrid search** - FTS5 keyword + semantic vectors + graph
- **Auto-capture** - Errors and sessions logged automatically
- **Beliefs & predictions** - Confidence tracking, validation
- **Knowledge graph** - Entities, relationships, spreading activation
- **Dream mode** - AI-powered consolidation
- **Memory decay** - FSRS-6 algorithm (natural forgetting)

## Hooks

The plugin registers these hooks:

| Hook | Purpose | Timeout |
|------|---------|---------|
| Setup | Install ai-iq, initialize DB | 120s |
| SessionStart | Check memory system health | 5s |
| PostToolUse | Capture failed commands | 30s |
| Stop | Auto-snapshot session | 60s |

## Storage

Memories are stored in `~/.ai-iq/memories.db` by default. Customize with:

```bash
export AI_IQ_DB_PATH="/path/to/project/.ai-iq/memories.db"
export AI_IQ_PROJECT="MyProject"
```

## Skills

The plugin provides a `memory` skill that teaches Claude how to:
- Add and search memories effectively
- Create beliefs and predictions
- Use the knowledge graph
- Maintain memory health
- Run dream mode for consolidation

See `.claude-plugin/skills/memory/SKILL.md` for full documentation.

## Differentiators vs claude-mem

| Feature | AI-IQ | claude-mem |
|---------|-------|------------|
| **Portability** | Single SQLite file | SQLite + Chroma + MCP |
| **Python API** | ✓ `from ai_iq import Memory` | ✗ CLI only |
| **Beliefs** | ✓ Confidence tracking | ✗ |
| **Predictions** | ✓ Validation over time | ✗ |
| **Knowledge graph** | ✓ Entities + relationships | ✗ |
| **Dream mode** | ✓ AI consolidation | ✗ |
| **Memory decay** | ✓ FSRS-6 algorithm | Time-based |
| **Vector search** | sqlite-vec (built-in) | Chroma (external) |
| **Framework** | Any Python agent | Claude Code only |

## Troubleshooting

### memory-tool not found

```bash
pip install ai-iq
export PATH="$PATH:$HOME/.local/bin"
```

### Plugin not loading

```bash
# Check plugin directory
ls -la ~/.claude/plugins/marketplaces/kobie3717/ai-iq/.claude-plugin/

# Verify plugin.json exists
cat ~/.claude/plugins/marketplaces/kobie3717/ai-iq/.claude-plugin/plugin.json
```

### Database errors

```bash
# Check database
memory-tool stats

# Repair if needed
sqlite3 ~/.ai-iq/memories.db "PRAGMA integrity_check;"
```

## Documentation

- [Main README](README.md) - Quick start
- [Python API](PYTHON_API.md) - Programmatic usage
- [Architecture](ARCHITECTURE.md) - System design
- [Examples](examples/) - Sample code
- [Plugin README](PLUGIN_README.md) - Plugin-specific docs

## Links

- **GitHub**: https://github.com/kobie3717/ai-iq
- **PyPI**: https://pypi.org/project/ai-iq/
- **Issues**: https://github.com/kobie3717/ai-iq/issues
- **Discord**: https://discord.gg/Y2jCXNGgE

## License

MIT - See [LICENSE](LICENSE)
