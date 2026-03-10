#!/bin/bash

# AI Memory SQLite - Error Hook
# Designed for Claude Code "PostToolUse" hook
# Captures failed Bash commands as error memories

# Use MEMORY_TOOL environment variable if set, otherwise default to 'memory-tool'
MT="${MEMORY_TOOL:-memory-tool}"

# Check if memory-tool is available
if ! command -v "$MT" &> /dev/null; then
    # Silently exit if memory-tool is not installed
    exit 0
fi

# Read JSON from stdin (Claude Code PostToolUse format)
INPUT=$(cat)

# Extract tool name
TOOL=$(echo "$INPUT" | grep -o '"tool":"[^"]*"' | cut -d'"' -f4)

# Only process Bash tool invocations
if [ "$TOOL" != "Bash" ]; then
    exit 0
fi

# Extract exit code
EXIT_CODE=$(echo "$INPUT" | grep -o '"exitCode":[0-9]*' | cut -d':' -f2)

# Only process non-zero exits (errors)
if [ -z "$EXIT_CODE" ] || [ "$EXIT_CODE" -eq 0 ]; then
    exit 0
fi

# Extract command (handle escaped quotes and newlines)
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('parameters', {}).get('command', 'unknown command'))
except:
    print('unknown command')
" 2>/dev/null || echo "unknown command")

# Extract error output (stderr or stdout if stderr is empty)
ERROR=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    result = data.get('result', {})
    stderr = result.get('stderr', '').strip()
    stdout = result.get('stdout', '').strip()
    error = stderr if stderr else stdout
    # Limit to first 500 chars
    print(error[:500] if error else 'Command failed with no output')
except:
    print('Command failed')
" 2>/dev/null || echo "Command failed")

# Log the error via memory-tool
"$MT" log-error "$COMMAND" "$ERROR" "$EXIT_CODE" 2>/dev/null || true

exit 0
