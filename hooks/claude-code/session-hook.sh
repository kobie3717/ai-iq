#!/bin/bash

# AI Memory SQLite - Session Hook
# Designed for Claude Code "Stop" hook
# Runs auto-snapshot, decay, export, and daily backup check

# Use MEMORY_TOOL environment variable if set, otherwise default to 'memory-tool'
MT="${MEMORY_TOOL:-memory-tool}"

# Check if memory-tool is available
if ! command -v "$MT" &> /dev/null; then
    # Silently exit if memory-tool is not installed
    exit 0
fi

# Auto-snapshot: capture session changes from git/file modifications
"$MT" auto-snapshot 2>/dev/null || true

# Decay: flag stale memories, deprioritize old ones
"$MT" decay 2>/dev/null || true

# Export: regenerate MEMORY.md from database
"$MT" export 2>/dev/null || true

# Daily backup check: only backup once per day
BACKUP_MARKER="${XDG_DATA_HOME:-$HOME/.local/share}/ai-memory/.last_backup"
TODAY=$(date +%Y-%m-%d)

if [ ! -f "$BACKUP_MARKER" ] || [ "$(cat "$BACKUP_MARKER" 2>/dev/null)" != "$TODAY" ]; then
    "$MT" backup 2>/dev/null || true
    echo "$TODAY" > "$BACKUP_MARKER"
fi
