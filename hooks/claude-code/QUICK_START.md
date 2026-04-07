# AI-IQ Claude Code Plugin - Quick Start

## One-Command Install

```bash
pip install ai-iq && cd $(pip show ai-iq | grep Location | cut -d' ' -f2)/../../../ai-iq && bash hooks/claude-code/install.sh
```

Or step-by-step:

```bash
# 1. Install AI-IQ
pip install ai-iq

# 2. Clone or navigate to AI-IQ repo
cd /path/to/ai-iq

# 3. Run installer
bash hooks/claude-code/install.sh

# 4. Add to your project's CLAUDE.md
cat hooks/claude-code/CLAUDE.md.example >> /your/project/CLAUDE.md
```

## What You Get

✅ **Auto-capture errors** - Failed Bash commands logged automatically  
✅ **Auto-snapshot sessions** - Git/file changes captured on session end  
✅ **Auto-export context** - MEMORY.md regenerated for next session  
✅ **Auto-maintain** - Daily decay, backup, cleanup (optional cron)  

## Verify Installation

```bash
# Test hooks
bash hooks/claude-code/test-hooks.sh

# Check stats
memory-tool stats

# View your memory
cat ~/.local/share/ai-memory/MEMORY.md
```

## Basic Commands

```bash
# Search memories
memory-tool search "docker"

# Add memory
memory-tool add learning "Always use --network=host for Redis" --project MyApp

# List pending TODOs
memory-tool pending

# Run dream mode (consolidate duplicates)
memory-tool dream

# View most accessed memories
memory-tool hot
```

## File Locations

- **Hooks**: `~/.claude/hooks/ai-iq-*.sh`
- **Config**: `~/.claude/settings.json`
- **Database**: `~/.local/share/ai-memory/memories.db`
- **Context**: `~/.local/share/ai-memory/MEMORY.md`
- **Backups**: `~/.local/share/ai-memory/backups/`

## Troubleshooting

**Hooks not running?**
```bash
ls -la ~/.claude/hooks/ai-iq-*.sh  # Check permissions
cat ~/.claude/settings.json | grep hooks  # Check config
```

**memory-tool not found?**
```bash
which memory-tool
pip show ai-iq
echo $PATH | grep .local/bin
```

**Database errors?**
```bash
memory-tool backup  # Backup first
mv ~/.local/share/ai-memory/memories.db{,.backup}
memory-tool stats  # Reinitialize
```

## Full Documentation

- **Complete guide**: [PLUGIN_README.md](PLUGIN_README.md)
- **Package info**: [PACKAGE_INFO.md](PACKAGE_INFO.md)
- **CLAUDE.md template**: [CLAUDE.md.example](CLAUDE.md.example)
- **GitHub**: https://github.com/kobie3717/ai-iq

## Support

- GitHub Issues: https://github.com/kobie3717/ai-iq/issues
- Run tests: `bash hooks/claude-code/test-hooks.sh`
- Check stats: `memory-tool stats`
