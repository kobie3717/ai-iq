# AI-IQ Claude Code Plugin Package

This directory contains the official Claude Code plugin for AI-IQ persistent memory system.

## Package Contents

```
hooks/claude-code/
├── install.sh                # Automated installer script
├── error-hook.sh             # PostToolUse hook (auto-captures failed Bash commands)
├── session-hook.sh           # Stop hook (auto-snapshots, decay, export, backup)
├── session-start-hook.sh     # SessionStart hook (logs session timeline)
├── daily-maintenance.sh      # Daily cron job (dream, decay, gc, backup)
├── test-hooks.sh             # Test suite for hook validation
├── PLUGIN_README.md          # Complete plugin documentation
├── CLAUDE.md.example         # Template for CLAUDE.md integration
├── README.md                 # Integration guide (existing)
└── settings.json.example     # Settings format reference (existing)
```

## Quick Start

```bash
# 1. Install AI-IQ if not already installed
pip install ai-iq

# 2. Run the automated installer
cd /path/to/ai-iq
bash hooks/claude-code/install.sh

# 3. Add to your project's CLAUDE.md
cat hooks/claude-code/CLAUDE.md.example >> /your/project/CLAUDE.md
```

## What Gets Installed

### Hook Scripts (copied to `~/.claude/hooks/`)

1. **ai-iq-error-hook.sh** (PostToolUse hook)
   - Triggers after every Bash command
   - Captures non-zero exit codes
   - Logs command + error output via `memory-tool log-error`

2. **ai-iq-session-hook.sh** (Stop hook)
   - Triggers when Claude Code session ends
   - Runs `memory-tool auto-snapshot` (detects git/file changes)
   - Runs `memory-tool decay` (flags stale memories)
   - Runs `memory-tool export` (regenerates MEMORY.md)
   - Daily backup check (once per day)

3. **ai-iq-session-start-hook.sh** (SessionStart hook)
   - Triggers when Claude Code session starts
   - Logs session start with 7-day expiry for timeline tracking

4. **ai-iq-daily-maintenance.sh** (optional cron)
   - Runs `memory-tool dream` (consolidate duplicates)
   - Runs `memory-tool decay` (flag stale memories)
   - Runs `memory-tool gc` (garbage collect deleted memories)
   - Runs `memory-tool backup` (create SQLite backup)
   - Logs to `~/.local/share/ai-memory/logs/daily-maintenance.log`

### Configuration (added to `~/.claude/settings.json`)

The installer adds hook configurations in the correct Claude Code format:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-error-hook.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-start-hook.sh"
          }
        ]
      }
    ]
  }
}
```

## Hook Lifecycle

### Session Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Session Start (SessionStart hook)                        │
│    • Log session start timestamp                            │
│    • Claude loads MEMORY.md automatically                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. During Session (PostToolUse hook)                        │
│    • Every Bash command monitored                           │
│    • Non-zero exits → captured as error memories            │
│    • Deduplication prevents spam                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Session End (Stop hook)                                  │
│    • Auto-snapshot (git diff + file changes)                │
│    • Decay (flag stale, update priorities)                  │
│    • Export (regenerate MEMORY.md)                          │
│    • Backup (once per day)                                  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Daily 3:17 AM (optional cron)                            │
│    • Dream mode (consolidate duplicates)                    │
│    • Decay (FSRS-6 algorithm)                               │
│    • Garbage collection (remove old deleted)                │
│    • Backup (create timestamped copy)                       │
└─────────────────────────────────────────────────────────────┘
```

## Testing

Run the test suite to verify installation:

```bash
cd /path/to/ai-iq
bash hooks/claude-code/test-hooks.sh
```

Tests verify:
1. memory-tool is installed
2. Hook scripts exist and are executable
3. Hooks run without errors
4. Errors are captured in memory database
5. MEMORY.md is generated
6. Basic memory operations work

## Manual Installation

If you prefer manual setup or need to merge with existing hooks:

### 1. Copy Hook Scripts

```bash
mkdir -p ~/.claude/hooks
cp hooks/claude-code/error-hook.sh ~/.claude/hooks/ai-iq-error-hook.sh
cp hooks/claude-code/session-hook.sh ~/.claude/hooks/ai-iq-session-hook.sh
cp hooks/claude-code/session-start-hook.sh ~/.claude/hooks/ai-iq-session-start-hook.sh
chmod +x ~/.claude/hooks/ai-iq-*.sh
```

### 2. Edit `~/.claude/settings.json`

If you already have hooks, merge the AI-IQ hooks into the existing arrays. Example:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-hook.sh"
          },
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/my-existing-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-error-hook.sh"
          }
        ]
      },
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/my-other-hook.mjs"
          }
        ]
      }
    ]
  }
}
```

### 3. Add CLAUDE.md Section

```bash
cat hooks/claude-code/CLAUDE.md.example >> /your/project/CLAUDE.md
```

Then edit your CLAUDE.md to add project-specific context.

### 4. (Optional) Install Daily Cron

```bash
cp hooks/claude-code/daily-maintenance.sh ~/.claude/hooks/ai-iq-daily-maintenance.sh
chmod +x ~/.claude/hooks/ai-iq-daily-maintenance.sh

# Add cron job (runs at 3:17 AM daily)
(crontab -l 2>/dev/null; echo "17 3 * * * bash ~/.claude/hooks/ai-iq-daily-maintenance.sh") | crontab -
```

## Customization

### Environment Variables

- `MEMORY_TOOL`: Path to memory-tool binary (default: `memory-tool`)
- `MEMORY_DIR`: Memory database directory (default: `~/.local/share/ai-memory`)

Set in `~/.bashrc` or `~/.zshrc`:

```bash
export MEMORY_TOOL=/custom/path/to/memory-tool
export MEMORY_DIR=/custom/path/to/memory
```

### Hook Behavior

All hooks fail silently if memory-tool is not installed. This ensures they don't break Claude Code if AI-IQ is not set up.

To debug hooks, run them manually:

```bash
# Test session-start hook
bash ~/.claude/hooks/ai-iq-session-start-hook.sh

# Test error hook with mock data
echo '{"tool_name":"Bash","tool_input":{"command":"false"},"tool_result":"Command failed\nExit code: 1"}' | bash ~/.claude/hooks/ai-iq-error-hook.sh

# Test session hook
bash ~/.claude/hooks/ai-iq-session-hook.sh
```

## Uninstalling

1. Remove hook entries from `~/.claude/settings.json`
2. Remove hook scripts: `rm ~/.claude/hooks/ai-iq-*.sh`
3. Remove cron job: `crontab -e` and delete the ai-iq-daily-maintenance line
4. (Optional) Uninstall AI-IQ: `pip uninstall ai-iq`

Your memory database at `~/.local/share/ai-memory/` will be preserved for future use.

## Troubleshooting

### Hooks not running

1. Check permissions:
   ```bash
   ls -la ~/.claude/hooks/ai-iq-*.sh
   # Should show -rwxr-xr-x
   ```

2. Test manually (see Customization section above)

3. Check Claude Code settings:
   ```bash
   cat ~/.claude/settings.json | grep -A 20 hooks
   ```

### memory-tool not found

1. Verify installation:
   ```bash
   which memory-tool
   pip show ai-iq
   ```

2. Ensure pip bin directory is in PATH:
   ```bash
   echo $PATH | grep -E "(\.local/bin|site-packages)"
   ```

3. Reinstall if needed:
   ```bash
   pip install --user ai-iq
   ```

### Database errors

1. Check database location:
   ```bash
   ls -la ~/.local/share/ai-memory/memories.db
   ```

2. Check permissions:
   ```bash
   ls -ld ~/.local/share/ai-memory
   ```

3. Reinitialize if corrupted:
   ```bash
   memory-tool backup  # Backup first!
   mv ~/.local/share/ai-memory/memories.db ~/.local/share/ai-memory/memories.db.backup
   memory-tool stats  # Reinitializes database
   ```

## File Locations

After installation:

- **Hook scripts**: `~/.claude/hooks/ai-iq-*.sh`
- **Configuration**: `~/.claude/settings.json`
- **Database**: `~/.local/share/ai-memory/memories.db`
- **Context file**: `~/.local/share/ai-memory/MEMORY.md`
- **Backups**: `~/.local/share/ai-memory/backups/`
- **Logs**: `~/.local/share/ai-memory/logs/`

## Support

- **Plugin README**: [PLUGIN_README.md](PLUGIN_README.md)
- **Integration guide**: [README.md](README.md)
- **Main repository**: https://github.com/kobie3717/ai-iq
- **Issues**: https://github.com/kobie3717/ai-iq/issues

## License

MIT License - see LICENSE file in the main repository.
