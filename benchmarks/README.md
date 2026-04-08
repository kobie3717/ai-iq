# AI-IQ Benchmarks

This directory contains benchmark scripts for evaluating AI-IQ's memory retrieval performance against established benchmarks.

## LongMemEval Benchmark

**Script:** `run_longmemeval.py`

Tests AI-IQ's hybrid search against the [LongMemEval benchmark](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) to measure retrieval accuracy on long conversation histories (~115k tokens per question).

### Reference Performance

- **MemPalace**: 96.6% R@5 (reference system from paper)

### Quick Start

```bash
# Full benchmark (500 questions, ~30-60 minutes)
cd /root/ai-memory-sqlite
MEMORY_DB=/tmp/longmemeval-test.db python3 benchmarks/run_longmemeval.py --cleanup

# Test run (5 questions)
MEMORY_DB=/tmp/longmemeval-test.db python3 benchmarks/run_longmemeval.py --limit 5 --cleanup
```

### Usage

```bash
python3 benchmarks/run_longmemeval.py [OPTIONS]

Options:
  --variant {s,m,l}    Dataset variant (default: s for small [500 questions])
  --limit N            Test with only N questions
  --top-k K            Retrieve top-K results (default: 5 for R@5 metric)
  --output PATH        Save detailed results JSON (default: /tmp/longmemeval-results.json)
  --cleanup            Remove test database after run
```

### How It Works

1. **Download**: Downloads LongMemEval dataset from Hugging Face (cached in `/tmp/longmemeval/`)
2. **Ingest**: Each question has multiple "haystack sessions" (chat histories). All sessions are ingested as memories with:
   - `wing='longmemeval'` - namespace for the benchmark
   - `room=q{idx}` - unique room per question
   - `tags={session_id}` - session identifier
3. **Query**: For each question, searches using AI-IQ's hybrid search (FTS + vector)
4. **Score**: Computes R@5 (recall at top 5) - did the gold session appear in top 5 results?
5. **Report**: Prints accuracy, comparison to MemPalace, and saves detailed results

### Dataset Variants

- **S (small)**: 500 questions - Recommended for full benchmark run (~6-10 hours estimated)
- **M (medium)**: More questions - Very long run time
- **Oracle**: Oracle baseline - Different structure

**Note**: Each question has ~50 haystack sessions that need embedding, making the benchmark compute-intensive. A 3-question test takes ~3 minutes.

### Example Output

```
==================================================================
AI-IQ LONGMEMEVAL BENCHMARK
==================================================================
Database: /tmp/longmemeval-test.db
Variant: S
Limit: 3 questions (TEST MODE)

[1/3] Ingesting question 0... Querying... ✗ R@5=0.0%
[2/3] Ingesting question 1... Querying... ✗ R@5=0.0%
[3/3] Ingesting question 2... Querying... ✓ R@5=33.3%

==================================================================
LONGMEMEVAL BENCHMARK RESULTS
==================================================================
Total Questions: 3
Correct: 1
R@5: 33.33%
------------------------------------------------------------------
AI-IQ:      33.3%
MemPalace:  96.6%  (reference)
Difference: -63.3%
==================================================================

Sample Results (first 5):
  ✗ Q0: What degree did I graduate with?
     Gold: ['answer_280352e9']
     Retrieved: ['sharegpt_QZMeA7V_17', 'esm,react,sharegpt_T1EiHWI_13', ...]

  ✓ Q2: Where did I redeem a $5 coupon on coffee creamer?
     Gold: ['answer_d61669c7']
     Retrieved: ['answer_d61669c7,dns', 'auth,esm,sharegpt_MKMWjX0_25', ...]

Total time: 176.0s (58.68s per question)
```

**Note**: The test run above shows 33% accuracy on 3 questions. Full benchmark (500 questions) would take ~8 hours. Performance optimization and tuning may be needed to reach MemPalace's 96.6% benchmark.

### Implementation Notes

- **Isolated Database**: Uses temporary DB at `/tmp/longmemeval-test.db` (set via `MEMORY_DB` env var)
  - **IMPORTANT**: Requires `memory_tool/config.py` to respect `MEMORY_DB` environment variable (fixed in this commit)
- **No Deduplication**: Uses `skip_dedup=True` to preserve exact benchmark data
- **Hybrid Search**: Leverages AI-IQ's FTS + vector search with RRF fusion
- **Metadata Filtering**: Uses `wing`/`room` to scope searches to specific question contexts
- **Session Encoding**: Each session's messages concatenated as single memory with session_id in tags
- **Auto-Tagging**: AI-IQ's auto-tagging adds extra tags (e.g., `answer_d61669c7,dns`), handled by substring matching
- **Verbosity**: Logging set to ERROR level to suppress warnings during benchmark

### Troubleshooting

**ImportError: No module named 'memory_tool'**
```bash
# Install AI-IQ in development mode
cd /root/ai-memory-sqlite
pip install -e .
```

**Database locked errors**
```bash
# Ensure no other process is using the test DB
rm -f /tmp/longmemeval-test.db*
```

**Out of memory**
- Use `--limit` to test with fewer questions
- Small variant (S) should work on systems with 4GB+ RAM

### Extending

To test other search modes:

```python
# Edit query_question() function to use different modes:
results, _, _ = search_memories(
    query=question_text,
    mode='semantic',  # or 'keyword', 'hybrid'
    wing='longmemeval',
    room=room_id
)
```

### Citation

If you use this benchmark in research:

```bibtex
@inproceedings{longmemeval2024,
  title={LongMemEval: Benchmarking Long-Term Memory in LLMs},
  author={Wu, Xiaoyue and others},
  booktitle={ICLR 2025},
  year={2024}
}
```

## Adding New Benchmarks

To add a new benchmark:

1. Create `run_{benchmark_name}.py` in this directory
2. Follow the pattern:
   - Set `MEMORY_DB` env var BEFORE importing memory_tool
   - Use `wing` parameter to namespace benchmark data
   - Use `room` parameter to scope searches
   - Print comparison to reference systems
   - Add `--cleanup` flag
3. Document in this README
