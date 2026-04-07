# Claude Code Integration Guide

This guide shows you how to integrate the AI-IQ system with Claude Code, enabling persistent memory across all your coding sessions.

## Overview

Once integrated, the memory system will:
- **Auto-capture errors** from failed Bash commands
- **Auto-snapshot sessions** when you stop working (detecting git commits and file changes)
- **Auto-export MEMORY.md** for Claude to read at the start of each session
- **Auto-maintain** the database (decay stale memories, backup daily)

## Prerequisites

- Claude Code CLI installed
- Python 3.8+ and SQLite 3.37+
- Bash shell (Linux/macOS)

## Installation Steps

### 1. Install memory-tool

From the repository root:

```bash
bash scripts/install.sh
```

This will:
- Install memory-tool to `~/.local/share/ai-iq/`
- Create a symlink at `~/.local/bin/memory-tool`
- Add `~/.local/bin` to your PATH (if not already there)
- Initialize the database

After installation, restart your shell or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

Verify installation:
```bash
memory-tool stats
```

### 2. Configure Claude Code Hooks

Claude Code supports lifecycle hooks that run at specific times. We'll configure two hooks:

#### a. Locate your Claude Code settings

Claude Code settings are typically at:
- Linux/macOS: `~/.config/claude-code/settings.json`
- Create the directory if it doesn't exist:
  ```bash
  mkdir -p ~/.config/claude-code
  ```

#### b. Copy hook scripts

```bash
# Create hooks directory
mkdir -p ~/.local/share/ai-iq/hooks

# Copy hook scripts
cp hooks/claude-code/session-hook.sh ~/.local/share/ai-iq/hooks/
cp hooks/claude-code/error-hook.sh ~/.local/share/ai-iq/hooks/

# Make them executable
chmod +x ~/.local/share/ai-iq/hooks/*.sh
```

#### c. Add hooks to settings.json

Edit `~/.config/claude-code/settings.json` (create if it doesn't exist):

```json
{
  "hooks": {
    "Stop": [
      "bash ~/.local/share/ai-iq/hooks/session-hook.sh"
    ],
    "PostToolUse": [
      "bash ~/.local/share/ai-iq/hooks/error-hook.sh"
    ]
  }
}
```

**Note**: If you already have other hooks, add these to the existing arrays.

### 3. Add Memory Instructions to CLAUDE.md

Add the memory system documentation to your project's `CLAUDE.md` file so Claude knows how to use it.

#### Option A: Copy the example section

```bash
# In your project directory
cat /path/to/ai-iq/hooks/claude-code/CLAUDE.md.example >> CLAUDE.md
```

Then edit `CLAUDE.md` to add your project-specific context.

#### Option B: Manual integration

Copy the "Persistent Memory System" section from `CLAUDE.md.example` into your project's `CLAUDE.md` file.

### 4. Set Up Daily Maintenance (Optional but Recommended)

Add a daily cron job to run maintenance tasks:

```bash
# Open crontab editor
crontab -e

# Add this line (runs at 3:17 AM daily)
17 3 * * * bash ~/.local/share/ai-iq/hooks/daily-maintenance.sh
```

Or copy the maintenance script:
```bash
cp hooks/claude-code/daily-maintenance.sh ~/.local/share/ai-iq/hooks/
chmod +x ~/.local/share/ai-iq/hooks/daily-maintenance.sh
```

### 5. Verify Everything Works

#### Test the Stop hook:
```bash
bash ~/.local/share/ai-iq/hooks/session-hook.sh
memory-tool stats
```

#### Test the PostToolUse hook:
```bash
# Create a mock PostToolUse event
echo '{"tool":"Bash","parameters":{"command":"false"},"result":{"exitCode":1,"stderr":"Command failed"}}' | bash ~/.local/share/ai-iq/hooks/error-hook.sh

# Check if error was captured
memory-tool list --category error
```

#### Test memory operations:
```bash
memory-tool add learning "Test memory from setup"
memory-tool search "test memory"
memory-tool list
memory-tool stats
```

## Usage

### Basic Workflow

1. **Start a Claude Code session**: MEMORY.md is auto-loaded with context from previous sessions
2. **Work on your project**: Claude uses memory to avoid repeating mistakes
3. **Errors are auto-captured**: When Bash commands fail, they're logged automatically
4. **End session**: Stop hook runs auto-snapshot, decay, export, and backup
5. **Next session**: Claude sees what happened last time in the "Last Session" section

### Manual Memory Management

You can also add memories manually during a session:

```bash
# Remember a decision
memory-tool add decision "Using PostgreSQL instead of MySQL for better JSON support" --project MyApp

# Remember a learning
memory-tool add learning "Always run migrations before deploying" --tags deployment,database

# Add a TODO
memory-tool add pending "Implement rate limiting on API endpoints" --priority 8 --expires 2026-04-01

# Search memories
memory-tool search "rate limiting"

# List project-specific memories
memory-tool list --project MyApp

# Show pending TODOs
memory-tool pending
```

### Project-Specific Memory

The system auto-detects projects based on:
- Current working directory
- Git repository name
- Explicit `--project` flag

To ensure memories are properly scoped:
```bash
# Set a consistent project name
memory-tool add project "MyApp: E-commerce platform in /home/user/myapp" --project MyApp
```

## Advanced Features

### Semantic Search (Optional)

For better search results using AI embeddings:

```bash
bash scripts/setup-embedding-model.sh
```

Then use:
```bash
memory-tool search "authentication issues" --semantic
memory-tool search "rate limiting"  # Hybrid is default (best of both worlds)
```

### Knowledge Graph

Track structured relationships:

```bash
# Add entities
memory-tool graph add-entity "UserAPI" "service" "REST API for user management"
memory-tool graph add-entity "AuthService" "service" "JWT authentication service"

# Add relationships
memory-tool graph add-relationship "UserAPI" "AuthService" "depends_on"

# Set properties
memory-tool graph set-fact "UserAPI" "port" "3000"
memory-tool graph set-fact "UserAPI" "url" "https://api.example.com"

# Query the graph
memory-tool graph get "UserAPI"
memory-tool graph spread "UserAPI" 2  # Find all related entities within 2 hops
```

### Conflict Detection

Find and merge duplicate or conflicting memories:

```bash
memory-tool conflicts
memory-tool merge 42 43  # Merge duplicate memories
```

## Troubleshooting

### Hooks not running

1. Check hook permissions:
   ```bash
   ls -la ~/.local/share/ai-iq/hooks/
   # Should show -rwxr-xr-x
   ```

2. Test hooks manually:
   ```bash
   bash ~/.local/share/ai-iq/hooks/session-hook.sh
   echo '{"tool":"Bash","parameters":{"command":"ls"},"result":{"exitCode":0}}' | bash ~/.local/share/ai-iq/hooks/error-hook.sh
   ```

3. Check Claude Code settings:
   ```bash
   cat ~/.config/claude-code/settings.json
   ```

### memory-tool not found

1. Check installation:
   ```bash
   which memory-tool
   ls -la ~/.local/bin/memory-tool
   ```

2. Ensure `~/.local/bin` is in PATH:
   ```bash
   echo $PATH | grep ".local/bin"
   ```

3. Restart your shell after installation

### Database errors

1. Check database location:
   ```bash
   ls -la ~/.local/share/ai-iq/memories.db
   ```

2. Reinitialize if corrupted:
   ```bash
   memory-tool backup  # Backup first!
   mv ~/.local/share/ai-iq/memories.db ~/.local/share/ai-iq/memories.db.backup
   memory-tool --init
   ```

3. Restore from backup:
   ```bash
   memory-tool restore ~/.local/share/ai-iq/backups/memories_YYYYMMDD_HHMMSS.db
   ```

## File Locations

- **Database**: `~/.local/share/ai-iq/memories.db`
- **Auto-generated context**: `~/.local/share/ai-iq/MEMORY.md`
- **Backups**: `~/.local/share/ai-iq/backups/`
- **Logs**: `~/.local/share/ai-iq/logs/`
- **Models**: `~/.local/share/ai-iq/models/` (if semantic search enabled)
- **Hooks**: `~/.local/share/ai-iq/hooks/`
- **Tool**: `~/.local/bin/memory-tool` → `~/.local/share/ai-iq/memory-tool.py`

## Customization

### Change memory directory

Set the `MEMORY_DIR` environment variable:

```bash
export MEMORY_DIR=/custom/path/to/memory
```

Add to your `~/.bashrc` or `~/.zshrc` to make it permanent.

### Change memory-tool path

If you install memory-tool to a custom location, set `MEMORY_TOOL`:

```bash
export MEMORY_TOOL=/custom/path/to/memory-tool
```

The hooks will automatically use this path.

### Customize decay settings

Edit memory-tool.py and adjust the decay thresholds in the `decay()` function.

## Best Practices

1. **Review MEMORY.md regularly**: Check what Claude is seeing at the start of each session
2. **Clean up pending items**: Delete completed TODOs with `memory-tool delete <id>`
3. **Use expiry dates**: Add `--expires YYYY-MM-DD` for time-sensitive TODOs
4. **Scope to projects**: Use `--project` to keep memories organized
5. **Tag consistently**: Use common tags (api, database, deployment, etc.)
6. **Resolve conflicts**: Run `memory-tool conflicts` weekly and merge duplicates
7. **Backup regularly**: Backups are automatic, but run `memory-tool backup` before major changes

## Getting Help

- **Documentation**: See README.md in the repository
- **Examples**: Check hooks/claude-code/CLAUDE.md.example
- **Issues**: Report bugs on GitHub
- **Stats**: Run `memory-tool stats` to see system health

## Next Steps

After setup:
1. Add some initial memories about your project
2. Start a Claude Code session and verify MEMORY.md is loaded
3. Make some changes and stop the session to test auto-snapshot
4. Trigger an error to test auto-capture
5. Search your memories to verify everything works

Happy coding with persistent memory!
