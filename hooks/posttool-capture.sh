#!/bin/bash
# AI-IQ PostToolUse Hook - Comprehensive Tool Execution Capture
# Captures ALL tool executions to session log (jsonl)
# On failures: saves to AI-IQ as error memory (existing behavior)
# On success: logs to session file, promotes to memory if pattern appears 3+ times
# Exit 0 always - never blocks execution

SESSION_LOG="/tmp/ai-iq-session-$(date +%Y-%m-%d).jsonl"
PATTERN_COUNT_FILE="/tmp/ai-iq-patterns.json"
MIN_PATTERN_FREQUENCY=3

# Read JSON from stdin (format: {"tool_name": "...", "tool_input": {...}, "tool_result": "..."})
read -r -d '' INPUT_JSON

# Parse JSON using jq if available, otherwise exit gracefully
if ! command -v jq &>/dev/null; then
  exit 0
fi

TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$INPUT_JSON" | jq -c '.tool_input // {}')
TOOL_RESULT=$(echo "$INPUT_JSON" | jq -r '.tool_result // empty')

# Skip if empty
if [[ -z "$TOOL_NAME" ]]; then
  exit 0
fi

# Initialize timestamp
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Function to extract command from tool input
extract_command() {
  local tool="$1"
  local input="$2"

  case "$tool" in
    Bash)
      echo "$input" | jq -r '.command // empty' | head -c 200
      ;;
    Edit|Write)
      echo "$input" | jq -r '.file_path // empty'
      ;;
    Read)
      echo "$input" | jq -r '.file_path // empty'
      ;;
    Grep|Glob)
      echo "$input" | jq -r '.pattern // empty'
      ;;
    *)
      echo "$tool"
      ;;
  esac
}

COMMAND=$(extract_command "$TOOL_NAME" "$TOOL_INPUT")

# Skip if no meaningful command extracted
if [[ -z "$COMMAND" || "$COMMAND" == "null" ]]; then
  exit 0
fi

# Determine exit code/success status
EXIT_CODE=0
SUCCESS="true"

if [[ "$TOOL_NAME" == "Bash" ]]; then
  # Check for "Exit code: N" in result
  if echo "$TOOL_RESULT" | grep -q "Exit code:"; then
    EXIT_CODE=$(echo "$TOOL_RESULT" | grep -oP 'Exit code: \K\d+' | head -1)
    if [[ "$EXIT_CODE" -ne 0 ]]; then
      SUCCESS="false"
    fi
  fi
fi

# 1. Log ALL executions to session log (jsonl)
cat >> "$SESSION_LOG" <<EOF
{"timestamp":"$TIMESTAMP","tool":"$TOOL_NAME","command":"${COMMAND//\"/\\\"}","exit_code":$EXIT_CODE,"success":$SUCCESS}
EOF

# 2. On FAILURE: save to AI-IQ as error memory (existing behavior)
if [[ "$SUCCESS" == "false" ]]; then
  # Extract first 200 chars of error message
  ERROR_MSG=$(echo "$TOOL_RESULT" | head -c 200 | tr '\n' ' ')

  # Add to AI-IQ as error memory (with content hash dedup - will skip if duplicate within 30s)
  memory-tool add error "Bash error: $COMMAND | $ERROR_MSG" \
    --tags hook,auto-capture,error \
    --source hook 2>/dev/null || true

  exit 0
fi

# 3. On SUCCESS: check if command pattern is frequent (3+ occurrences)
# Extract command pattern (first word or tool name)
PATTERN=$(echo "$COMMAND" | awk '{print $1}')

# Skip trivial patterns
case "$PATTERN" in
  ls|cd|pwd|cat|head|tail|echo|git|npm|which|whoami|date|df|free)
    exit 0
    ;;
esac

# Load pattern counts (simple JSON: {"pattern": count})
if [[ ! -f "$PATTERN_COUNT_FILE" ]]; then
  echo '{}' > "$PATTERN_COUNT_FILE"
fi

# Increment pattern count using jq
PATTERN_COUNT=$(jq -r --arg p "$PATTERN" '.[$p] // 0' "$PATTERN_COUNT_FILE")
NEW_COUNT=$((PATTERN_COUNT + 1))

# Update pattern count file
jq --arg p "$PATTERN" --argjson n "$NEW_COUNT" '.[$p] = $n' "$PATTERN_COUNT_FILE" > "${PATTERN_COUNT_FILE}.tmp"
mv "${PATTERN_COUNT_FILE}.tmp" "$PATTERN_COUNT_FILE"

# If pattern appears 3+ times for the first time, promote to memory
if [[ "$NEW_COUNT" -eq "$MIN_PATTERN_FREQUENCY" ]]; then
  # Add workflow memory (dedup will prevent duplicates)
  memory-tool add workflow "Frequent command pattern: $PATTERN (used $NEW_COUNT times)" \
    --tags hook,auto-capture,frequent-pattern \
    --source hook 2>/dev/null || true
fi

exit 0
