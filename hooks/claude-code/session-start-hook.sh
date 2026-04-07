#!/bin/bash

# AI Memory SQLite - Session Start Hook
# Designed for Claude Code "SessionStart" hook
# Logs session start for timeline tracking

# Use MEMORY_TOOL environment variable if set, otherwise default to 'memory-tool'
MT="${MEMORY_TOOL:-memory-tool}"

# Check if memory-tool is available
if ! command -v "$MT" &> /dev/null; then
    # Silently exit if memory-tool is not installed
    exit 0
fi

# Log session start with 7-day expiry (auto-cleanup)
EXPIRY=$(date -d '+7 days' +%Y-%m-%d 2>/dev/null || date -v+7d +%Y-%m-%d 2>/dev/null)
"$MT" add workflow "Session started" --source hook-auto --expires "$EXPIRY" --skip-dedup 2>/dev/null || true

exit 0
