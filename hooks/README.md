# AI-IQ Hooks

These hooks integrate with Claude Code to automatically capture session activity.

## Architecture Overview (Inspired by claude-mem)

AI-IQ implements three key architectural patterns from claude-mem:

### 1. Content Hash Deduplication (30-second window)
Prevents duplicate observations from rapid tool executions using SHA256 content hashing.
- **Implementation**: `memory_tool/memory_ops.py:smart_ingest()` (lines 212-227)
- **Hash format**: SHA256(category:content).slice(0,16)
- **Window**: 30 seconds sliding window
- **Database**: `content_hash` column with index on memories table

### 2. Progressive Disclosure with Token Budgets
Provides 3-tier retrieval for efficient context management:
- **Index view** (default): Compact results with token estimates (~5-100 tokens per result)
- **Budget mode**: `--budget N` flag auto-truncates results to fit token limit
- **Full detail**: `memory-tool get <id>` for deep dive (~200-1000 tokens per memory)

### 3. Comprehensive Tool Capture
Captures ALL tool executions (not just errors) with smart filtering and rate limiting.
- **Captures**: Bash commands (success + errors), file edits, significant operations
- **Filters**: Skips noisy commands (ls, cd, pwd, git status)
- **Rate limit**: Max 1 capture per 10 seconds
- **Storage**: Session logs (JSONL) + promoted patterns (memories)

## PostTool Capture Hook (Bash - Enhanced) - NEW

**File**: `posttool-capture.sh`  
**Type**: PostToolUse hook  
**Purpose**: Comprehensive tool execution capture - logs ALL tools, promotes frequent patterns to memory

### Features

- **Logs ALL tool executions** to session log: `/tmp/ai-iq-session-YYYY-MM-DD.jsonl`
- **On failures**: Saves error to AI-IQ memory (with 30s dedup window)
- **On success**: Tracks command patterns, promotes frequently-used patterns (3+ occurrences) to memory
- **Pattern tracking**: Identifies workflow patterns (e.g., "pytest used 3 times" → adds workflow memory)
- **Lightweight**: Session log for analytics, memory only for errors + frequent patterns
- **Smart dedup**: 30-second content-hash dedup prevents rapid-fire duplicates

### Installation

```bash
# Create hooks directory if it doesn't exist
mkdir -p ~/.claude/hooks

# Install the hook
cp /root/ai-iq/hooks/posttool-capture.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/posttool-capture.sh

# Requires jq for JSON parsing
sudo apt-get install -y jq  # or brew install jq on macOS
```

### Usage

Once installed, the hook runs automatically. Check activity:

```bash
# View today's session log
tail -f /tmp/ai-iq-session-$(date +%Y-%m-%d).jsonl

# View captured errors in AI-IQ
memory-tool list --category error --tag hook

# View frequent patterns
memory-tool search "Frequent command pattern"

# Show only errors from session log
jq 'select(.success == false)' /tmp/ai-iq-session-$(date +%Y-%m-%d).jsonl

# Show command frequency
jq -r '.command' /tmp/ai-iq-session-$(date +%Y-%m-%d).jsonl | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
```

### Customization

Edit `/root/ai-iq/hooks/posttool-capture.sh` to customize:

- `MIN_PATTERN_FREQUENCY=3` - Change threshold for pattern promotion (default: 3)
- Skip patterns - Add to the case statement to ignore specific commands
- Session log path - Change `SESSION_LOG` variable

---

## Tool Capture Hook (Node.js - Original)

**File**: `tool-capture.mjs`  
**Type**: PostToolUse hook  
**Purpose**: Captures significant tool executions as workflow memories in AI-IQ database

### Features

- Captures **errors** from failed Bash commands → `error` memories
- Captures **file edits/writes** → `workflow` memories
- Captures **significant commands** (git push, deploy, npm publish, etc.) → `workflow` memories
- Captures **agent spawns** → `workflow` memories
- **Rate limited**: Max 1 capture per 10 seconds to prevent flooding
- **Smart filtering**: Skips trivial commands (ls, cat, echo, etc.)
- **Dedup-aware**: AI-IQ's 30-second dedup window prevents exact duplicates

### Installation

```bash
# Create hooks directory if it doesn't exist
mkdir -p ~/.claude/hooks

# Install the hook
cp /root/ai-iq/hooks/tool-capture.mjs ~/.claude/hooks/
chmod +x ~/.claude/hooks/tool-capture.mjs
```

### Usage

Once installed, the hook runs automatically. View captured workflow memories:

```bash
# Search for recent workflow captures
memory-tool search "auto-capture"

# List all workflow memories
memory-tool list --tag hook

# List all errors
memory-tool list --category error
```

## Session Logger Hook (Analytics)

**File**: `session-logger.mjs`  
**Type**: PostToolUse hook  
**Purpose**: Logs ALL tool executions (Bash, Read, Edit, Write, Glob, Grep) to `/tmp/ai-iq-session-log.jsonl` for analysis (does NOT add to memory database)

### Installation

```bash
# Create hooks directory if it doesn't exist
mkdir -p ~/.claude/hooks

# Install the hook
cp /root/ai-iq/hooks/session-logger.mjs ~/.claude/hooks/
chmod +x ~/.claude/hooks/session-logger.mjs
```

### Usage

Once installed, the hook will automatically log every tool execution. View the log with:

```bash
# View last 50 tool executions
memory-tool session-log

# View last 100 executions
memory-tool session-log --limit 100

# View only failed commands
memory-tool session-log --errors

# View raw JSONL log
cat /tmp/ai-iq-session-log.jsonl
```

### Log Format

Each log entry is a JSON object with:
- `timestamp`: ISO 8601 timestamp
- `tool`: Tool name (Bash, Read, Edit, Write, Glob, Grep)
- Tool-specific fields:
  - **Bash**: `input` (command), `exit_code`, `output_preview` (first 100 chars)
  - **Read/Edit/Write**: `file_path`, `action`
  - **Glob/Grep**: `pattern`, `output_preview` (match count)

### Log Rotation

The log file is append-only and grows indefinitely. To clear it:

```bash
rm /tmp/ai-iq-session-log.jsonl
```

Or set up a cron job to rotate it daily:

```bash
# Add to crontab
0 0 * * * mv /tmp/ai-iq-session-log.jsonl /tmp/ai-iq-session-log-$(date +\%Y\%m\%d).jsonl && gzip /tmp/ai-iq-session-log-*.jsonl
```

## Testing & Verification

### Test Content Hash Deduplication

```bash
# Add a test memory
memory-tool add learning "Redis requires network_mode host"

# Try adding exact duplicate within 30s
memory-tool add learning "Redis requires network_mode host"
# Output: ⚡ DEDUP: Blocked duplicate within 30s window (matches #X)

# Wait 31 seconds, try again
sleep 31
memory-tool add learning "Redis requires network_mode host"
# Will create new memory (outside 30s window)
```

### Test Token Budget

```bash
# Search with no budget
memory-tool search "database"
# Output: 15 results (~2400 tokens total)

# Search with budget limit
memory-tool search "database" --budget 500
# Output: ⚠️ Token budget: showing 8/15 results (fits in ~480/500 tokens)
```

### Verify Hook Capture

```bash
# 1. Check hook is active
ls -lh ~/.claude/hooks/posttool-capture.sh

# 2. Execute a command
docker ps

# 3. Check session log
tail -1 /tmp/ai-iq-session-$(date +%Y-%m-%d).jsonl

# 4. Try duplicate within 30s window
docker ps
# Should be logged but not duplicated in memory (dedup window active)
```

## Progressive Disclosure Usage Examples

```bash
# 1. Quick scan (default compact mode)
memory-tool search "docker"
# Output: [7] learning | Docker needs... (2x) ⚡5.1 ~5tok
#         20 results (~1047 tokens total). Use --full for details...

# 2. Budget-aware retrieval (fits in agent's context window)
memory-tool search "authentication jwt" --budget 800
# Auto-truncates to ~800 tokens, shows X/Y results

# 3. Deep dive on specific memory
memory-tool get 42
# Full detail: content, tags, FSRS retention, importance, related memories (~200 tokens)

# 4. Full verbose mode (when you need all details)
memory-tool search "docker" --full
# Shows complete content, metadata, relations for all results
```

## Configuration

### Adjust Content Hash Window

Edit `/root/ai-iq/memory_tool/memory_ops.py` line ~217:

```python
recent_dupe = conn.execute("""
    SELECT id FROM memories
    WHERE content_hash = ?
    AND datetime(created_at) > datetime('now', '-30 seconds')  # Change window here
""", (content_hash,)).fetchone()
```

### Customize Rate Limiting

Edit hook file to adjust rate limit:

```bash
# In posttool-capture.sh
RATE_LIMIT_SECONDS=10  # Max 1 capture per 10 seconds

# In tool-capture.mjs
const RATE_LIMIT_SECONDS = 10;
```

### Skip Patterns

Add noisy commands to skip list in `tool-capture.mjs`:

```javascript
const SKIP_COMMANDS = new Set([
  'ls', 'cd', 'pwd', 'cat', 'echo',
  'git status', 'git log', 'git diff',
  // Add more...
]);
```

## Troubleshooting

### Hook not capturing

```bash
# Check hook permissions
chmod +x ~/.claude/hooks/posttool-capture.sh

# Test hook manually
cat test-hook-input.json | bash posttool-capture.sh
```

### Content hash not deduplicating

```bash
# Verify content_hash column exists
sqlite3 /root/ai-iq/memories.db "PRAGMA table_info(memories)" | grep content_hash

# Check index
sqlite3 /root/ai-iq/memories.db ".indexes memories" | grep content_hash

# If missing, reinit database
cd /root/ai-iq && python3 -c "from memory_tool.database import init_db; init_db()"
```

### Token estimates seem off

```bash
# Token estimates use word_count × 1.3 heuristic
# Compare estimate to actual:
memory-tool get 42 | grep "~"
# Shows estimated tokens

# For more accuracy, integrate a proper tokenizer
# (tiktoken for OpenAI, transformers for HuggingFace models)
```

## Hook Design Principles

- **Exit 0 always**: Hooks never block Claude Code execution
- **Fail silently**: Errors in hooks don't crash the agent
- **Minimal overhead**: Lightweight processing, no expensive operations
- **Privacy-aware**: Don't log sensitive data (passwords, tokens, full file contents)
- **Dedup-first**: Content hash dedup prevents memory bloat from repetitive commands
- **Progressive disclosure**: Token budgets enable efficient context management
