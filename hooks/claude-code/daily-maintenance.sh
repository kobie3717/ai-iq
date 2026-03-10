#!/bin/bash

# AI Memory SQLite - Daily Maintenance
# Designed to run as a daily cron job
# Runs decay, garbage collection, backup, and export

# Use MEMORY_TOOL environment variable if set, otherwise default to 'memory-tool'
MT="${MEMORY_TOOL:-memory-tool}"

# Check if memory-tool is available
if ! command -v "$MT" &> /dev/null; then
    echo "ERROR: memory-tool not found in PATH" >&2
    exit 1
fi

# Log file for cron output
LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ai-memory/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily-maintenance.log"

# Redirect output to log file
exec >> "$LOG_FILE" 2>&1

echo "=== AI Memory Daily Maintenance ==="
echo "Started: $(date)"
echo ""

# Decay: flag stale memories and deprioritize old ones
echo "Running decay..."
if "$MT" decay; then
    echo "  OK"
else
    echo "  FAILED (exit code: $?)"
fi

# Garbage collection: remove soft-deleted memories older than 180 days
echo "Running garbage collection..."
if "$MT" gc; then
    echo "  OK"
else
    echo "  FAILED (exit code: $?)"
fi

# Backup: create SQLite backup
echo "Running backup..."
if "$MT" backup; then
    echo "  OK"
else
    echo "  FAILED (exit code: $?)"
fi

# Export: regenerate MEMORY.md
echo "Exporting MEMORY.md..."
if "$MT" export; then
    echo "  OK"
else
    echo "  FAILED (exit code: $?)"
fi

echo ""
echo "Completed: $(date)"
echo "==============================="
echo ""
