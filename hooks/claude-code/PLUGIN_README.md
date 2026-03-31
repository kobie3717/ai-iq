# AI-IQ Claude Code Plugin

Persistent memory system for Claude Code with automatic error capture, session snapshots, and intelligent memory management.

## What This Plugin Does

Once installed, AI-IQ will automatically:

1. **Auto-capture errors**: Failed Bash commands are automatically logged as error memories
2. **Auto-snapshot sessions**: When you stop working, AI-IQ detects git commits and file changes to create a session summary
3. **Auto-export context**: Regenerates `MEMORY.md` for Claude to read at the start of each session
4. **Auto-maintain**: Runs decay, garbage collection, and backups
5. **Timeline tracking**: Logs session start times for better temporal context

## Quick Install

```bash
# Install AI-IQ if not already installed
pip install ai-iq

# Run the plugin installer
cd /path/to/ai-iq
bash hooks/claude-code/install.sh
```

The installer will:
- Check if `memory-tool` is installed
- Copy hook scripts to `~/.claude/hooks/`
- Configure hooks in `~/.claude/settings.json`
- Optionally install a daily maintenance cron job

## Manual Installation

If you prefer manual setup or need to merge with existing hooks:

### 1. Install AI-IQ

```bash
pip install ai-iq
```

### 2. Copy Hook Scripts

```bash
mkdir -p ~/.claude/hooks
cp hooks/claude-code/error-hook.sh ~/.claude/hooks/ai-iq-error-hook.sh
cp hooks/claude-code/session-hook.sh ~/.claude/hooks/ai-iq-session-hook.sh
cp hooks/claude-code/session-start-hook.sh ~/.claude/hooks/ai-iq-session-start-hook.sh
chmod +x ~/.claude/hooks/ai-iq-*.sh
```

### 3. Configure Hooks

Add to `~/.claude/settings.json` (merge with existing hooks if needed):

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

### 4. Add to Your Project's CLAUDE.md

Copy the AI-IQ section from `CLAUDE.md.example` to your project's `CLAUDE.md`:

```bash
cat hooks/claude-code/CLAUDE.md.example >> /your/project/CLAUDE.md
```

## Hook Details

### PostToolUse Hook (error-hook.sh)

- **Trigger**: After every Bash tool invocation
- **Condition**: Only activates on non-zero exit codes
- **Action**: Captures command and error output, calls `memory-tool log-error`
- **Silent**: Fails gracefully if memory-tool is not installed

### Stop Hook (session-hook.sh)

- **Trigger**: When Claude Code session ends
- **Actions**:
  1. `memory-tool auto-snapshot` - Detects git/file changes and creates session summary
  2. `memory-tool decay` - Flags stale memories using FSRS-6 algorithm
  3. `memory-tool export` - Regenerates MEMORY.md with smart context
  4. `memory-tool backup` - Daily backup check (once per day)

### SessionStart Hook (session-start-hook.sh)

- **Trigger**: When Claude Code session starts
- **Action**: Logs session start with 7-day expiry for timeline tracking
- **Silent**: Fails gracefully if memory-tool is not installed

## Daily Maintenance (Optional)

Install a daily cron job for background maintenance:

```bash
# Copy maintenance script
cp hooks/claude-code/daily-maintenance.sh ~/.claude/hooks/ai-iq-daily-maintenance.sh
chmod +x ~/.claude/hooks/ai-iq-daily-maintenance.sh

# Add cron job (runs at 3:17 AM daily)
(crontab -l 2>/dev/null; echo "17 3 * * * bash ~/.claude/hooks/ai-iq-daily-maintenance.sh") | crontab -
```

The daily maintenance runs:
- `memory-tool decay` - Flag stale memories
- `memory-tool gc` - Garbage collect old deleted memories (180 days)
- `memory-tool backup` - Create SQLite backup
- `memory-tool export` - Regenerate MEMORY.md

Logs are written to `~/.local/share/ai-memory/logs/daily-maintenance.log`

## Verifying Installation

### Test the hooks manually:

```bash
# Test session hook
bash ~/.claude/hooks/ai-iq-session-hook.sh
echo "Session hook completed"

# Test error hook (simulate failed command)
echo '{"tool_name":"Bash","tool_input":{"command":"false"},"tool_result":"Command failed\nExit code: 1"}' | bash ~/.claude/hooks/ai-iq-error-hook.sh
echo "Error hook completed"

# Check if error was captured
memory-tool list --category error
```

### Test memory operations:

```bash
# Add a test memory
memory-tool add learning "Testing AI-IQ integration" --project test

# Search for it
memory-tool search "testing"

# View stats
memory-tool stats

# Check MEMORY.md
cat ~/.local/share/ai-memory/MEMORY.md
```

## Using AI-IQ with Claude Code

### Automatic Memory Capture

Once installed, you don't need to do anything special. The hooks run automatically:

1. **Start a session**: Claude loads `MEMORY.md` automatically
2. **Work on your code**: Claude remembers past decisions and errors
3. **Hit an error**: The error is auto-captured (no manual logging needed)
4. **End the session**: Session is auto-snapshotted, memories decay, MEMORY.md is regenerated

### Manual Memory Management

You can also manage memories manually during a session:

```bash
# Remember a decision
memory-tool add decision "Using PostgreSQL instead of MySQL" --project MyApp

# Add a TODO with expiry
memory-tool add pending "Implement rate limiting" --priority 8 --expires 2026-04-15

# Search memories
memory-tool search "database"

# List project memories
memory-tool list --project MyApp

# Show pending TODOs
memory-tool pending

# Get smart suggestions
memory-tool next
```

### Advanced Features

```bash
# Hybrid search (semantic + keyword)
memory-tool search "authentication" --semantic

# Find conflicts/duplicates
memory-tool conflicts
memory-tool merge <id1> <id2>

# Dream mode (AI-powered cleanup)
memory-tool dream

# Track beliefs and predictions
memory-tool believe "PostgreSQL is the best choice" --confidence 0.8
memory-tool predict "Migration will complete by April 15" --deadline 2026-04-15

# View hot memories (frequently accessed, immune to decay)
memory-tool hot

# Knowledge graph
memory-tool graph add project MyApp "E-commerce platform"
memory-tool graph rel MyApp uses PostgreSQL
memory-tool graph spread MyApp 2
```

## File Locations

- **Database**: `~/.local/share/ai-memory/memories.db`
- **Auto-generated context**: `~/.local/share/ai-memory/MEMORY.md`
- **Backups**: `~/.local/share/ai-memory/backups/`
- **Logs**: `~/.local/share/ai-memory/logs/`
- **Hooks**: `~/.claude/hooks/ai-iq-*.sh`
- **Settings**: `~/.claude/settings.json`

## Customization

### Custom Memory Directory

Set the `MEMORY_DIR` environment variable:

```bash
export MEMORY_DIR=/custom/path/to/memory
```

Add to your `~/.bashrc` or `~/.zshrc` to make it permanent.

### Custom memory-tool Path

If you install memory-tool to a custom location:

```bash
export MEMORY_TOOL=/custom/path/to/memory-tool
```

The hooks will automatically use this path.

## Merging with Existing Hooks

If you already have Claude Code hooks, you need to merge the AI-IQ hooks into your existing configuration.

Example of merged hooks:

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
            "command": "bash ~/.claude/hooks/my-existing-stop-hook.sh"
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
            "command": "node ~/.claude/hooks/my-existing-hook.mjs"
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

### Hooks not running

1. Check hook permissions:
   ```bash
   ls -la ~/.claude/hooks/ai-iq-*.sh
   # Should show -rwxr-xr-x
   ```

2. Test hooks manually (see "Verifying Installation" section)

3. Check Claude Code settings:
   ```bash
   cat ~/.claude/settings.json | grep -A 20 hooks
   ```

### memory-tool not found

1. Check installation:
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
   # Should be writable by your user
   ```

3. Reinitialize if corrupted:
   ```bash
   memory-tool backup  # Backup first!
   mv ~/.local/share/ai-memory/memories.db ~/.local/share/ai-memory/memories.db.backup
   memory-tool stats  # This will reinitialize
   ```

## Uninstalling

To remove AI-IQ hooks from Claude Code:

1. Remove hooks from `~/.claude/settings.json` (delete the AI-IQ hook entries)
2. Remove hook scripts:
   ```bash
   rm ~/.claude/hooks/ai-iq-*.sh
   ```
3. Remove cron job (if installed):
   ```bash
   crontab -e
   # Delete the line with "ai-iq-daily-maintenance.sh"
   ```
4. Optionally uninstall AI-IQ:
   ```bash
   pip uninstall ai-iq
   ```

Your memory database will be preserved at `~/.local/share/ai-memory/` for future use.

## Learn More

- **Full documentation**: https://github.com/kobie3717/ai-iq
- **PyPI package**: https://pypi.org/project/ai-iq/
- **CLAUDE.md template**: `hooks/claude-code/CLAUDE.md.example`
- **Memory tool help**: `memory-tool --help`

## Support

For issues or questions:
- GitHub Issues: https://github.com/kobie3717/ai-iq/issues
- Check existing documentation in the AI-IQ repository
- Review the troubleshooting section above

## License

AI-IQ is MIT licensed. See LICENSE file in the main repository.
