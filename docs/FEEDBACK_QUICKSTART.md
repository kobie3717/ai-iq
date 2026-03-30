# Feedback System Quick Start

Get the self-learning feedback loop running in 5 minutes.

## 1. Check It's Working

The feedback system is built into AI-IQ v5+. Verify it's active:

```bash
cd /root/ai-iq
python3 -m pytest tests/test_feedback.py -v
```

All tests should pass (9/9).

## 2. Try It Manually

Add some test memories:

```bash
memory-tool add learning "Python asyncio for high concurrency" --tags python,asyncio --priority 5
memory-tool add learning "FastAPI dependency injection patterns" --tags python,fastapi --priority 5
memory-tool add learning "React hooks and state management" --tags react,hooks --priority 5
```

Search and note the search_id:

```bash
memory-tool search "python"
# [search_id:1]
```

"Use" one of the results:

```bash
memory-tool get 1
```

Log feedback:

```bash
memory-tool feedback 1 1
```

Check quality stats:

```bash
memory-tool search-quality
```

You'll see:
- Hit rate: 50% or higher
- The memory you used should appear in "Most Helpful"

## 3. Enable Auto-Feedback (Recommended)

Copy the hook to Claude's directory:

```bash
mkdir -p ~/.claude/hooks
cp /root/ai-iq/hooks/search-feedback.mjs ~/.claude/hooks/
```

Now feedback is automatic! Every time you:
1. Run `memory-tool search` → search_id captured
2. Run `memory-tool get/update/delete <id>` → marked as "used"
3. Start new search or end session → feedback logged

## 4. Watch It Learn

Run dream mode to apply learning:

```bash
memory-tool dream
```

This will:
- Consolidate duplicates
- Boost high-value memories
- Decay low-value memories
- Flag never-used memories as stale

Check the results:

```bash
memory-tool hot          # Show most accessed (immune to decay)
memory-tool search-quality  # Show hit rates and helpful/unhelpful memories
```

## 5. Monitor Over Time

Add to your cron (already done if you installed AI-IQ):

```cron
17 3 * * * cd /root/ai-iq && memory-tool dream
```

Dream mode runs nightly and:
- Extracts insights from transcripts
- Consolidates duplicates
- Normalizes dates
- **Applies feedback learning** ← NEW!

## What to Expect

### Week 1
- Search logs accumulate
- No visible changes yet (need 10+ searches per memory for learning)

### Week 2-4
- High-value memories boosted (easier to find)
- Low-value memories decayed (less noise in results)
- Never-used memories flagged as stale

### Month 2+
- Search quality noticeably better
- Less time wasted on irrelevant results
- Memory system "knows" what you actually use

## Troubleshooting

**No search logs in stats?**
- Make sure you're running searches that return results
- Check: `sqlite3 /root/ai-iq/memories.db "SELECT COUNT(*) FROM search_log"`

**Hook not working?**
- Verify hook is executable: `chmod +x ~/.claude/hooks/search-feedback.mjs`
- Check Claude's hook logs (if available)
- Use manual feedback as fallback

**No learning applied during dream?**
- Need 10+ searches per memory for boost/decay
- Need 20+ searches with 0 uses for stale flag
- Check: `memory-tool search-quality` to see if you have enough data

**Stats showing errors?**
- Run: `memory-tool stats` to see if search_log table exists
- Re-run: `memory-tool reindex` to rebuild vector index
- Check logs for SQL errors

## Next Steps

Once comfortable with the basics:

1. **Read the full docs**: `/root/ai-iq/docs/FEEDBACK_SYSTEM.md`
2. **Tune the thresholds**: Edit `/root/ai-iq/memory_tool/feedback.py`
   - `hit_rate > 0.80` (boost threshold)
   - `hit_rate < 0.20` (decay threshold)
   - `retrieve_count >= 20` (stale flag threshold)
3. **Add custom metrics**: Extend `get_search_quality_stats()` with your own KPIs
4. **Integrate with your workflow**: Use search_id in your own tools

## Key Commands Reference

```bash
# Search with feedback
memory-tool search "query"           # Returns search_id
memory-tool feedback <id> <used_ids> # Log which were used

# Quality reports
memory-tool search-quality           # Full report
memory-tool hot                      # Most accessed memories
memory-tool stats                    # Includes search quality summary

# Learning
memory-tool dream                    # Apply feedback learning (+ other maintenance)

# Testing
pytest tests/test_feedback.py       # Run feedback tests
```

## Success Metrics

Track these over time to measure improvement:

1. **Hit rate trending up** (target: >70%)
2. **Hot memories count increasing** (5+ accesses)
3. **Stale memories decreasing** (being cleaned up)
4. **Search latency stable** (<50ms on average)

Check monthly with:

```bash
memory-tool search-quality
memory-tool hot
memory-tool stale
```

---

**Result**: A memory system that learns from your usage and gets better over time. No manual curation needed!
