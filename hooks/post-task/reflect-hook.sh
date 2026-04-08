#!/bin/bash
# Post-task reflection hook
# Logs completed commands to a queue for later reflection processing
#
# Usage: Called automatically after significant bash commands complete
# Or manually: bash reflect-hook.sh <command> <exit_code>

QUEUE_FILE="/tmp/reflect-queue.jsonl"

# Get command and exit code
COMMAND="${1:-$BASH_COMMAND}"
EXIT_CODE="${2:-$?}"

# Only log significant commands (skip reads, simple lookups, etc.)
if [[ "$COMMAND" =~ ^(ls|cd|pwd|echo|cat|head|tail|grep|find)\ ]] || [[ -z "$COMMAND" ]]; then
    exit 0
fi

# Skip successful simple commands
if [[ $EXIT_CODE -eq 0 ]] && [[ ${#COMMAND} -lt 30 ]]; then
    exit 0
fi

# Create JSON entry
TIMESTAMP=$(date -Iseconds)
JSON_ENTRY=$(jq -n \
    --arg cmd "$COMMAND" \
    --arg code "$EXIT_CODE" \
    --arg ts "$TIMESTAMP" \
    '{command: $cmd, exit_code: ($code | tonumber), timestamp: $ts}')

# Append to queue
echo "$JSON_ENTRY" >> "$QUEUE_FILE"

# Keep queue size reasonable (last 100 entries)
if [[ -f "$QUEUE_FILE" ]]; then
    tail -100 "$QUEUE_FILE" > "${QUEUE_FILE}.tmp"
    mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
fi
