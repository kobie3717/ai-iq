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
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only process Bash tool calls
if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# Extract exit code from tool_result
EXIT_CODE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d.get('tool_result', '')
# Look for exit code in result
if 'Exit code' in str(r):
    import re
    m = re.search(r'Exit code[:\s]+(\d+)', str(r))
    if m: print(m.group(1))
    else: print('0')
else:
    print('0')
" 2>/dev/null)

# Only log non-zero exit codes
if [ "$EXIT_CODE" != "0" ] && [ -n "$EXIT_CODE" ]; then
    COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
i = d.get('tool_input', {})
print(i.get('command', '')[:150])
" 2>/dev/null)

    ERROR=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = str(d.get('tool_result', ''))
# Get last 3 meaningful lines
lines = [l.strip() for l in r.split('\n') if l.strip() and not l.startswith('Exit code')]
print('\n'.join(lines[-3:])[:300])
" 2>/dev/null)

    if [ -n "$COMMAND" ] && [ -n "$ERROR" ]; then
        "$MT" log-error "$COMMAND" "$ERROR" 2>/dev/null || true
    fi
fi

exit 0
