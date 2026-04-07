# Search Feedback & Learning System

**Status**: Phase 6 feature - Production ready (v5+)
**Purpose**: Self-learning feedback loop that improves memory quality over time

## Overview

The feedback system tracks which search results are actually used, then applies learning to:
- **Boost** high-value memories (retrieved often and used often)
- **Decay** low-value memories (retrieved often but rarely used)
- **Flag** useless memories (retrieved 20+ times but never used)

This creates a **self-improving memory system** that gets better with every search.

## Architecture

### 1. Search Logging (Automatic)

Every `memory-tool search` call logs:
- Query text
- Search mode (hybrid/keyword/semantic)
- Result IDs returned
- Result count
- Latency (ms)
- Timestamp

**Database table**: `search_log`

```sql
CREATE TABLE search_log (
    id INTEGER PRIMARY KEY,
    query TEXT NOT NULL,
    search_type TEXT DEFAULT 'hybrid',
    result_ids TEXT,              -- comma-separated IDs
    used_ids TEXT,                -- filled by feedback
    result_count INTEGER,
    hit_rate REAL,                -- used / results
    latency_ms INTEGER,
    created_at TEXT
);
```

### 2. Feedback Tracking (Manual or Automatic)

When a memory is actually used (read, updated, referenced), log it:

```bash
# Manual feedback
memory-tool feedback <search_id> <used_id1,used_id2>

# Automatic via hook (see hooks/search-feedback.mjs)
# Detects when `memory-tool get <id>` is run after a search
```

**What happens on feedback**:
1. Updates `search_log.used_ids` with the IDs that were used
2. Calculates `hit_rate` = used_count / result_count
3. Boosts `access_count` for used memories (+1)
4. Gently decays `priority` for retrieved-but-unused memories (-1, min 0)

### 3. Learning Application (Nightly via Dream)

Run as part of `memory-tool dream` (or manually via `apply_feedback_learning`):

```python
def apply_feedback_learning():
    # High performers: >80% hit rate over 10+ searches → priority +1
    # Low performers: <20% hit rate over 10+ searches → priority -1
    # Never used: 20+ retrievals, 0 uses → flag as stale
```

**Result**: Memory system learns which memories are valuable and which are noise.

## Usage

### View Search Quality

```bash
memory-tool search-quality
```

**Output**:
- Overall hit rates (7d, 30d, all time)
- Most helpful memories (high hit rate)
- Least helpful memories (low hit rate, candidates for cleanup)
- Most common queries and success rates
- Failing queries (0% hit rate)

### View Hot Memories

```bash
memory-tool hot
```

Shows memories with 5+ accesses (immune to decay).

### Manual Feedback

```bash
# Search
memory-tool search "python patterns"
# [search_id:42]

# Use some results
memory-tool get 123
memory-tool get 125

# Log feedback
memory-tool feedback 42 123,125
```

### Automatic Feedback (Recommended)

Install the Claude Code hook:

```bash
# Copy hook to Claude's hooks directory
cp /root/ai-iq/hooks/search-feedback.mjs ~/.claude/hooks/

# Hook automatically:
# 1. Captures search_id when you run memory-tool search
# 2. Tracks when you run memory-tool get/update/delete <id>
# 3. Logs feedback when you start a new search or end session
```

### Stats Integration

The `memory-tool stats` command now includes search quality:

```bash
memory-tool stats
# ...
# Search Quality:
#   Hit rate (7d): 75% (42 searches)
#   Hit rate (all): 68% (156 searches)
```

## How It Works: Example Flow

1. **User searches**: `memory-tool search "docker patterns"`
   - Returns 5 results: #10, #23, #45, #67, #89
   - Logs search_id=100 in `search_log`

2. **User reads/uses some**:
   - `memory-tool get 10` (reads it)
   - `memory-tool update 23 "..."` (edits it)
   - Ignores #45, #67, #89

3. **Feedback logged**: `memory-tool feedback 100 10,23`
   - Updates `search_log.used_ids = "10,23"`
   - Calculates `hit_rate = 2/5 = 0.40` (40%)
   - Boosts `access_count` for #10 and #23
   - Gently decays priority for #45, #67, #89

4. **Nightly learning** (via `memory-tool dream`):
   - Over time, if #10 and #23 consistently have high hit rates → priority boosted
   - If #45, #67, #89 consistently have low hit rates → priority decayed
   - If #89 is retrieved 20+ times but never used → flagged as stale

5. **Result**: Future searches return better results (high-value memories rank higher)

## Integration with Existing Features

### FSRS Spaced Repetition
- Feedback boosts `access_count`, which feeds into FSRS `fsrs_reps`
- High-value memories become immune to decay (`access_count >= 5`)

### Importance Scoring
- `access_count` increases `imp_frequency` score
- High-value memories get higher `imp_score`
- Higher priority in search results and MEMORY.md export

### Dream Mode
- Feedback learning runs automatically during `memory-tool dream`
- Consolidation considers feedback stats (high-value memories kept, low-value pruned)

### Decay System
- Hot memories (`access_count >= 5`) are immune to staleness
- Low-value memories (flagged by feedback) age faster

## Performance Impact

- **Search latency**: +1-2ms per search (logging overhead)
- **Feedback latency**: ~5ms per feedback call
- **Learning latency**: ~50-200ms (runs nightly, not blocking)
- **Storage**: ~50 bytes per search log entry

**Trade-off**: Tiny overhead for massive quality improvement over time.

## Testing

Run the feedback test suite:

```bash
cd /root/ai-iq
python3 -m pytest tests/test_feedback.py -v
```

**Coverage**: 9 tests covering:
- Search logging
- Feedback tracking
- Hit rate calculation
- Learning application
- Stats generation
- Edge cases (empty results, invalid IDs, etc.)

## Future Enhancements

### Phase 7 Ideas:
1. **Query expansion**: Learn which queries lead to successful results, suggest better queries
2. **Personalization**: Track per-user feedback for multi-user systems
3. **Context awareness**: Consider what task the user is working on
4. **Negative feedback**: Explicitly mark "bad" results that wasted time
5. **A/B testing**: Test different ranking algorithms, keep the best

### Potential Metrics:
- **Time-to-useful**: How long until user finds useful memory
- **Abandonment rate**: Searches that return results but user doesn't use any
- **Retry rate**: User searches again with different query (original failed)

## Design Decisions

### Why track feedback at all?
- **Problem**: Memory systems accumulate noise over time (outdated, duplicates, never-used)
- **Solution**: Track actual usage, prune based on real data instead of guessing

### Why hit rate instead of binary used/not-used?
- **Insight**: A search that returns 10 results with 1 useful is worse than 3 results with 2 useful
- **Metric**: Hit rate captures search quality, not just result quality

### Why gentle decay for unused results?
- **Reason**: Maybe the memory is still useful, just not for this query
- **Strategy**: Only flag as stale if retrieved 20+ times and never used (strong signal)

### Why automatic feedback via hooks?
- **UX**: Manual feedback is tedious, users won't do it
- **Automation**: Hook transparently tracks usage without user intervention
- **Accuracy**: Captures real behavior (what the user actually reads/edits)

## Integration with OpenClaw Bridge

The feedback system is **local to AI-IQ** and does not sync to OpenClaw by default.

**Rationale**: Search feedback is specific to the AI-IQ search algorithm. OpenClaw may use different search methods.

**Future**: Could add bidirectional feedback sync if both systems adopt the same feedback schema.

## Summary

**Before feedback system**: Memory system slowly fills with noise, search quality degrades over time.

**After feedback system**: Memory system learns what's valuable, automatically prunes noise, search quality improves over time.

**Result**: Self-improving AI memory that gets smarter with every search.
