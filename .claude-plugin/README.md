# AI-IQ Claude Code Plugin

This directory contains the Claude Code plugin configuration for AI-IQ.

## Files

- **plugin.json** - Plugin manifest (name, version, description, author)
- **marketplace.json** - Marketplace listing configuration
- **hooks.json** - Hook definitions (Setup, SessionStart, PostToolUse, Stop)
- **setup.sh** - Setup script (installs ai-iq, initializes DB)
- **CLAUDE.md** - Plugin-specific guidance for Claude

## Installation

### Via Marketplace

```bash
/plugin marketplace add kobie3717/ai-iq
/plugin install ai-iq
```

### Manual

```bash
cd ~/.claude/plugins/marketplaces
mkdir -p kobie3717
git clone https://github.com/kobie3717/ai-iq kobie3717/ai-iq
```

## Structure

```
.claude-plugin/
├── plugin.json        # Plugin manifest
├── marketplace.json   # Marketplace config
├── hooks.json         # Hook definitions
├── setup.sh          # Setup script
├── CLAUDE.md         # Plugin docs
└── README.md         # This file

skills/
└── memory/
    └── SKILL.md      # Memory skill documentation

hooks/
├── posttool-capture.sh    # Auto-capture hook
└── claude-code/
    ├── install.sh         # Full installer
    ├── session-hook.sh    # Stop hook
    └── ...
```

## Hooks

| Hook | Purpose | Timeout |
|------|---------|---------|
| Setup | Install ai-iq, initialize DB | 120s |
| SessionStart | Health check | 5s |
| PostToolUse | Capture failed commands | 30s |
| Stop | Auto-snapshot session | 60s |

## Skills

- **memory** - Complete memory system documentation

## Development

See [PLUGIN_TESTING.md](../PLUGIN_TESTING.md) for testing guide.

## Links

- [Main README](../README.md)
- [Plugin Guide](../CLAUDE_CODE_PLUGIN.md)
- [Testing Guide](../PLUGIN_TESTING.md)
- [Python API](../PYTHON_API.md)
