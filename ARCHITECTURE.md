# Architecture

Technical deep-dive into ai-memory-sqlite implementation.

## Database Schema

### Core Tables

#### memories
Primary storage for all memory entries.

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,              -- project/decision/preference/error/learning/pending/architecture/workflow/contact
    content TEXT NOT NULL,                -- Memory content (plain text)
    project TEXT DEFAULT NULL,            -- Associated project name
    tags TEXT DEFAULT '',                 -- Comma-separated tags
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    accessed_at TEXT DEFAULT NULL,        -- Last search access
    access_count INTEGER DEFAULT 0,       -- Search access counter
    priority INTEGER DEFAULT 0,           -- 0-10, auto-adjusts on access
    active INTEGER DEFAULT 1,             -- 0 = deleted/expired
    stale INTEGER DEFAULT 0,              -- 1 = flagged as stale
    expires_at TEXT DEFAULT NULL,         -- Auto-expire date
    source TEXT DEFAULT 'manual',         -- manual/import/auto-hook/openclaw-import
    topic_key TEXT DEFAULT NULL,          -- Unique key for topic upserts
    revision_count INTEGER DEFAULT 1      -- Update counter
);

CREATE INDEX idx_category ON memories(category);
CREATE INDEX idx_project ON memories(project);
CREATE INDEX idx_active ON memories(active);
CREATE INDEX idx_stale ON memories(stale);
CREATE INDEX idx_accessed ON memories(accessed_at);
CREATE INDEX idx_expires ON memories(expires_at);
CREATE INDEX idx_source ON memories(source);
CREATE UNIQUE INDEX idx_topic_key ON memories(topic_key) WHERE topic_key IS NOT NULL;
```

#### memories_fts
FTS5 full-text search index with triggers for auto-sync.

```sql
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content, tags, project, category,
    content='memories',
    content_rowid='id'
);

-- Triggers keep FTS in sync with memories table
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags, project, category)
    VALUES (new.id, new.content, new.tags, new.project, new.category);
END;

CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, project, category)
    VALUES ('delete', old.id, old.content, old.tags, old.project, old.category);
    INSERT INTO memories_fts(rowid, content, tags, project, category)
    VALUES (new.id, new.content, new.tags, new.project, new.category);
END;

CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, project, category)
    VALUES ('delete', old.id, old.content, old.tags, old.project, old.category);
END;
```

#### memory_vec
Vector embeddings using sqlite-vec extension.

```sql
CREATE VIRTUAL TABLE memory_vec USING vec0(
    embedding float[384]  -- all-MiniLM-L6-v2 dimensionality
);
```

Stores 384-dimensional embeddings aligned with `memories.id` rowids.

#### memory_relations
Bidirectional links between memories.

```sql
CREATE TABLE memory_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES memories(id),
    target_id INTEGER NOT NULL REFERENCES memories(id),
    relation_type TEXT DEFAULT 'related',
    created_at TEXT NOT NULL,
    UNIQUE(source_id, target_id)
);

CREATE INDEX idx_relations_source ON memory_relations(source_id);
CREATE INDEX idx_relations_target ON memory_relations(target_id);
```

Relations are bidirectional: queries check both `source_id` and `target_id`.

#### session_snapshots
Auto-generated session summaries.

```sql
CREATE TABLE session_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    project TEXT DEFAULT NULL,
    files_touched TEXT DEFAULT '',      -- JSON list of modified files
    memories_added TEXT DEFAULT '',     -- JSON list of memory IDs
    memories_updated TEXT DEFAULT '',   -- JSON list of memory IDs
    created_at TEXT NOT NULL
);
```

### Knowledge Graph Tables

#### graph_entities
Nodes in the knowledge graph.

```sql
CREATE TABLE graph_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL CHECK(type IN (
        'person', 'project', 'org', 'feature',
        'concept', 'tool', 'service'
    )),
    summary TEXT DEFAULT '',
    importance INTEGER DEFAULT 3,       -- 0-5, affects spreading activation
    created_at TEXT,
    updated_at TEXT
);
```

#### graph_relationships
Directed edges in the knowledge graph.

```sql
CREATE TABLE graph_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    to_entity_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK(relation_type IN (
        'knows', 'works_on', 'owns', 'depends_on',
        'built_by', 'uses', 'blocks', 'related_to'
    )),
    note TEXT DEFAULT '',
    created_at TEXT,
    UNIQUE(from_entity_id, to_entity_id, relation_type)
);
```

#### graph_facts
Key-value metadata on entities.

```sql
CREATE TABLE graph_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,        -- 0.0-1.0
    source TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(entity_id, key)
);
```

#### graph_memory_links
Links between memories and entities.

```sql
CREATE TABLE graph_memory_links (
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (memory_id, entity_id)
);
```

Auto-linking detects entity names in memory content.

## Hybrid Search Algorithm

Combines three strategies with Reciprocal Rank Fusion (RRF).

### 1. Keyword Search (FTS5)

```sql
SELECT id, rank, content FROM memories_fts
WHERE memories_fts MATCH ?
ORDER BY rank
LIMIT 50
```

Fast BM25-based ranking. Good for exact matches and technical terms.

### 2. Semantic Search (Vector Similarity)

```python
def embed_text(text):
    """Generate 384-dim embedding using all-MiniLM-L6-v2"""
    # Tokenize
    encoding = tokenizer.encode(text)
    input_ids = np.array([encoding.ids], dtype=np.int64)
    attention_mask = np.array([encoding.attention_mask], dtype=np.int64)

    # ONNX inference
    outputs = session.run(None, {
        'input_ids': input_ids,
        'attention_mask': attention_mask
    })

    # Mean pooling with attention mask
    token_embeddings = outputs[0]
    attention_expanded = np.expand_dims(attention_mask, -1)
    sum_embeddings = np.sum(token_embeddings * attention_expanded, axis=1)
    sum_mask = np.clip(np.sum(attention_expanded, axis=1), a_min=1e-9, a_max=None)
    mean_embeddings = sum_embeddings / sum_mask

    # L2 normalize
    norms = np.linalg.norm(mean_embeddings, axis=1, keepdims=True)
    normalized = mean_embeddings / np.clip(norms, a_min=1e-9, a_max=None)

    return normalized.astype(np.float32).tobytes()
```

Vector search uses cosine similarity via sqlite-vec:

```sql
SELECT rowid, distance FROM memory_vec
WHERE embedding MATCH ?
ORDER BY distance
LIMIT 50
```

### 3. Graph Traversal (Spreading Activation)

Starting from entities mentioned in query:

1. Find entities matching query terms
2. Compute activation scores (importance × depth_decay)
3. Traverse relationships up to depth N
4. Retrieve memories linked to activated entities

```python
def spreading_activation(entity_name, depth=2, decay=0.5):
    """Breadth-first spreading activation"""
    activated = {entity_name: 1.0}
    visited = set()

    for d in range(depth):
        current_depth_entities = [...]
        for entity in current_depth_entities:
            # Find neighbors via relationships
            neighbors = get_neighbors(entity)
            for neighbor, importance in neighbors:
                activation = activated[entity] * (decay ** (d+1)) * (importance / 5.0)
                activated[neighbor] = max(activated.get(neighbor, 0), activation)

    # Get memories linked to activated entities
    memory_scores = aggregate_memory_scores(activated)
    return memory_scores
```

### Reciprocal Rank Fusion (RRF)

Merge results from all three strategies:

```python
def rrf_fusion(keyword_results, semantic_results, graph_results, k=60):
    """Combine ranked lists using RRF"""
    scores = defaultdict(float)

    for rank, (id, _) in enumerate(keyword_results):
        scores[id] += 1.0 / (k + rank + 1)

    for rank, (id, _) in enumerate(semantic_results):
        scores[id] += 1.0 / (k + rank + 1)

    for rank, (id, score) in enumerate(graph_results):
        scores[id] += 1.0 / (k + rank + 1)

    # Sort by combined score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**k=60** is the RRF constant (higher values = more equal weighting).

## Smart Ingestion Flow

Prevents duplicates and detects conflicts using SequenceMatcher similarity.

```python
def smart_ingest(new_content, category, project):
    """
    Returns: (action, similar_id, similarity)
    Actions: SKIP, UPDATE, SUPERSEDE, CREATE
    """
    # Find existing memories in same category/project
    existing = query_existing(category, project)

    for mem in existing:
        similarity = SequenceMatcher(None, new_content.lower(), mem.content.lower()).ratio()

        if similarity > 0.85:
            return ('SKIP', mem.id, similarity)  # Duplicate

        elif similarity > 0.65:
            # Prompt user for conflict resolution
            return ('CONFLICT', mem.id, similarity)

    return ('CREATE', None, 0.0)
```

**Similarity thresholds**:
- **> 85%** - Block as duplicate
- **65-85%** - Warn, suggest merge/update/supersede
- **< 65%** - Create new memory

**User actions on conflicts**:
1. **UPDATE** - Replace old content with new
2. **SUPERSEDE** - Mark old as superseded, create new
3. **MERGE** - Combine content, preserve older timestamp
4. **SKIP** - Discard new content
5. **FORCE** - Create anyway (ignore similarity)

## Embedding Pipeline

### Model Download

On first run with `--semantic`:

```python
def download_model():
    """Download all-MiniLM-L6-v2 from HuggingFace"""
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id="sentence-transformers/all-MiniLM-L6-v2",
        allow_patterns=["tokenizer.json", "onnx/model.onnx"],
        local_dir=MODEL_DIR
    )
```

Model size: ~90MB (tokenizer + ONNX weights).

### Tokenization

Uses HuggingFace Tokenizers (Rust-based, fast):

```python
tokenizer = Tokenizer.from_file("tokenizer.json")
tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
tokenizer.enable_truncation(max_length=256)
```

### ONNX Inference

CPU-optimized inference with ONNXRuntime:

```python
session = ort.InferenceSession(
    "onnx/model.onnx",
    providers=['CPUExecutionProvider']
)

outputs = session.run(None, {
    'input_ids': input_ids,
    'attention_mask': attention_mask
})
```

### Mean Pooling + Normalization

```python
# Mean pooling (weighted by attention mask)
token_embeddings = outputs[0]  # [batch, seq_len, hidden_dim]
attention_expanded = np.expand_dims(attention_mask, -1)
sum_embeddings = np.sum(token_embeddings * attention_expanded, axis=1)
sum_mask = np.clip(np.sum(attention_expanded, axis=1), a_min=1e-9, a_max=None)
mean_embeddings = sum_embeddings / sum_mask

# L2 normalize
norms = np.linalg.norm(mean_embeddings, axis=1, keepdims=True)
normalized = mean_embeddings / np.clip(norms, a_min=1e-9, a_max=None)
```

Final embedding: 384-dim float32 vector, L2-normalized for cosine similarity.

## Hook Integration Architecture

### PostToolUse Hook (Error Capture)

Claude Code calls this after every Bash tool use.

**Input**: JSON via stdin
```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "npm test"},
  "tool_result": "stderr output\nExit code: 1"
}
```

**Flow**:
1. Parse JSON from stdin
2. Check if `tool_name == "Bash"`
3. Extract exit code from result
4. If non-zero, extract command + stderr
5. Call `memory-tool log-error`

**Implementation** (`error-hook.sh`):
```bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; ...")
EXIT_CODE=$(echo "$INPUT" | python3 -c "...")

if [ "$EXIT_CODE" != "0" ]; then
    memory-tool log-error "$COMMAND" "$ERROR"
fi
```

### Stop Hook (Session Snapshot)

Called when Claude Code session ends.

**Flow**:
1. `memory-tool auto-snapshot` - Detect git/file changes
2. `memory-tool decay` - Flag stale memories
3. `memory-tool export` - Regenerate MEMORY.md
4. `memory-tool backup` - Create daily backup (if none today)

**Implementation** (`session-hook.sh`):
```bash
memory-tool auto-snapshot 2>/dev/null
memory-tool decay 2>/dev/null
memory-tool export 2>/dev/null

TODAY=$(date +%Y%m%d)
if [ ! -f "$BACKUP_DIR/memories_${TODAY}"*.db ]; then
    memory-tool backup 2>/dev/null
fi
```

### Auto-Snapshot Detection

Detects changes via git + file timestamps:

```python
def auto_snapshot():
    """Generate snapshot from git/file changes"""
    cwd = os.getcwd()
    project = detect_project(cwd)

    # Try git first
    if is_git_repo(cwd):
        diff_summary = run_git_diff_summary()
        recent_commits = run_git_log()
        files_touched = parse_git_status()
    else:
        # Fallback: file timestamps
        files_touched = find_recently_modified_files(cwd)

    # Detect new/updated memories
    recent_memories = query_recent_memories(hours=2)

    # Generate summary
    summary = format_snapshot_summary(
        diff_summary, recent_commits,
        files_touched, recent_memories
    )

    insert_snapshot(summary, project, files_touched)
```

## Auto-Tagging System

Content-based keyword detection:

```python
AUTO_TAG_RULES = {
    "pm2": ["pm2"],
    "whatsapp": ["whatsapp", "baileys", "webhook"],
    "database": ["postgresql", "psql", "prisma", "migration"],
    "auth": ["jwt", "login", "password", "token"],
    "nginx": ["nginx", "reverse proxy", "ssl"],
    # ... 15+ rules
}

def auto_tag(content):
    """Extract tags from content"""
    content_lower = content.lower()
    detected = []

    for tag, keywords in AUTO_TAG_RULES.items():
        if any(kw in content_lower for kw in keywords):
            detected.append(tag)

    return detected
```

Applied on `add` and `update`, merged with user-provided tags.

## Decay System

Automated staleness and priority management.

**Thresholds**:
- Pending items: 30 days
- General memories: 90 days
- Deprioritize: 60 days without access

**Flow**:
```python
def decay():
    """Run decay algorithm"""
    now = datetime.now()

    # Flag stale pending items (30 days)
    cursor.execute("""
        UPDATE memories SET stale = 1
        WHERE category = 'pending'
          AND active = 1
          AND datetime(created_at, '+30 days') < ?
    """, (now,))

    # Flag stale general memories (90 days, no access)
    cursor.execute("""
        UPDATE memories SET stale = 1
        WHERE category != 'pending'
          AND active = 1
          AND (accessed_at IS NULL AND datetime(created_at, '+90 days') < ?)
          OR (accessed_at IS NOT NULL AND datetime(accessed_at, '+90 days') < ?)
    """, (now, now))

    # Deprioritize (60 days, reduce by 1)
    cursor.execute("""
        UPDATE memories SET priority = MAX(0, priority - 1)
        WHERE active = 1
          AND priority > 0
          AND (accessed_at IS NULL AND datetime(created_at, '+60 days') < ?)
          OR (accessed_at IS NOT NULL AND datetime(accessed_at, '+60 days') < ?)
    """, (now, now))

    # Expire (past expires_at)
    cursor.execute("""
        UPDATE memories SET active = 0
        WHERE active = 1 AND expires_at IS NOT NULL AND expires_at < ?
    """, (now,))
```

Run via:
- Stop hook (every session)
- Daily cron (3:17 AM)
- Manual: `memory-tool decay`

## Progressive Disclosure (MEMORY.md)

Intelligent context export with budget cap.

**Budget**: 5KB hard limit (prevents context overflow)

**Priority order**:
1. Project-specific memories (if project detected)
2. Recent session snapshots (last 3)
3. Pending items (15 max)
4. High-priority memories (priority >= 7)
5. Recent learnings/decisions (30 days)

**Format**:
```markdown
# Persistent Memory
_Updated: 2026-03-10 | v4_

## Last Session (2026-03-09)
<snapshot summary>

## Active Projects
<project summaries>

## Pending / TODO
<actionable items>

## Key Decisions
<important decisions>

_[Over budget — run `memory-tool topics` for full view]_
```

If budget exceeded, show truncated + budget message.

## Topic File Export

Generate separate `.md` files per project:

```bash
memory-tool topics
```

Creates `topics/WhatsAuction.md`, `topics/FlashVault.md`, etc.

Each file contains all memories for that project, organized by category.

**Use case**: When MEMORY.md hits budget cap, load specific project topic file.

## OpenClaw Bridge

Bidirectional sync with OpenClaw's workspace format.

**Directory**: `/root/.openclaw/workspace/memory/`

**Exported files**:
- `claude-code-bridge.md` - Session handoff (recent changes, pending)
- `graph.json` - Full knowledge graph export
- `topics/<project>.json` - Per-project memories in JSON

**Sync state** (`.sync-state.json`):
```json
{
  "last_sync_to": "2026-03-10T04:49:00",
  "last_sync_from": "2026-03-10T04:49:00",
  "files_exported": 22,
  "files_imported": 0
}
```

**Dedup on import**: Checksums prevent re-importing same content.

## Performance Characteristics

**Database size**: ~2MB for 100 memories + embeddings + graph

**Search speed**:
- Keyword (FTS): < 5ms
- Semantic (vec): < 50ms (50 results)
- Graph traversal: < 100ms (depth 2)
- Hybrid (RRF): < 150ms total

**Embedding speed**: ~10ms per text (ONNX CPU)

**Bulk reindex**: ~1 second for 100 memories

**Memory usage**: ~200MB with model loaded (ONNX session + embeddings)

## Error Handling

**Graceful degradation**:
- Missing sqlite-vec → Disable semantic search, use FTS + graph only
- Missing model files → Download on first `--semantic` use
- Corrupted embeddings → Auto-reindex on next search
- DB locked → Retry with exponential backoff

**Backup safety**:
- Restore creates pre-restore backup
- Backup retention: 7 days
- Atomic writes with WAL mode

## Future Optimizations

**Planned**:
- Quantized embeddings (float16) for 50% size reduction
- Approximate nearest neighbor (HNSW) for >1000 memories
- Async embedding pipeline for bulk imports
- Incremental graph updates (avoid full export)

**Not planned**:
- Cloud sync (privacy-first design)
- Multi-user support (single-user tool)
- Web UI (CLI-first philosophy)
