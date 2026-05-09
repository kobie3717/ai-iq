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

## Internal Retrieval Quality Benchmark

**Script:** `run.py` (module: `benchmarks.run`)

Tests AI-IQ's search modes (keyword, semantic, hybrid) against curated test corpus to measure retrieval quality improvements from PPR, adaptive-k, and causal routing.

### Quick Start

```bash
# Run full benchmark with formatted table output
python3 -m benchmarks.run

# Output JSON for programmatic analysis
python3 -m benchmarks.run --json

# Suppress progress messages
python3 -m benchmarks.run --quiet
```

### What It Measures

**Metrics:**
- **Recall@k**: Fraction of queries where relevant memory appears in top-k results
  - R@1: Relevant memory is the top result
  - R@3: Relevant memory in top 3
  - R@5: Relevant memory in top 5
- **MRR**: Mean Reciprocal Rank (1/rank of first relevant hit, 0 if none found)
- **Latency**: Average search time in milliseconds

**Search Modes:**
- **keyword**: FTS5 full-text search only
- **semantic**: Vector embedding search only
- **hybrid**: RRF fusion of keyword + semantic (includes PPR, adaptive-k, causal routing)

**Query Types:**
- **Keyword** (7 queries): Exact terms present in memories
- **Semantic** (8 queries): Paraphrased, no exact term matches
- **Causal** (10 queries): Why/caused/led-to patterns

### Test Corpus

35 curated memories + 25 labeled queries spanning:
- Infrastructure/DevOps (Redis, Docker, Nginx, PM2, SSL, PostgreSQL)
- WhatsApp/Baileys (rate limits, bans, errors, session bugs)
- Python/AI (SQLite FTS5, embeddings, RRF, ONNX, PPR)
- Frontend (React, Tailwind, Vite, CSS), Backend (Express, Node.js)
- Security/Compliance (GDPR, EU AI Act, JWT)
- Payments (Stripe, PayFast)

### Example Output

```
======================================================================
AI-IQ RETRIEVAL BENCHMARK
======================================================================

── Query type: ALL ──
Mode            R@1    R@3    R@5    MRR      ms
---------------------------------------------
keyword      28.0% 28.0% 28.0% 0.280  169.0ms
semantic     84.0% 100.0% 100.0% 0.900  429.0ms
hybrid       80.0% 96.0% 96.0% 0.872  263.0ms

── Query type: KEYWORD ──
Mode            R@1    R@3    R@5    MRR      ms
---------------------------------------------
keyword      85.7% 85.7% 85.7% 0.857  283.0ms
semantic     85.7% 100.0% 100.0% 0.905  501.6ms
hybrid       100.0% 100.0% 100.0% 1.000  284.9ms

── Query type: SEMANTIC ──
Mode            R@1    R@3    R@5    MRR      ms
---------------------------------------------
keyword      12.5% 12.5% 12.5% 0.125   83.8ms
semantic     75.0% 100.0% 100.0% 0.833  272.5ms
hybrid       75.0% 87.5% 87.5% 0.810  237.5ms

── Query type: CAUSAL ──
Mode            R@1    R@3    R@5    MRR      ms
---------------------------------------------
keyword       0.0%  0.0%  0.0% 0.000  237.1ms
semantic     90.0% 100.0% 100.0% 0.950  270.4ms
hybrid       70.0% 100.0% 100.0% 0.833  230.8ms

======================================================================
Legend: R@k = Recall@k  MRR = Mean Reciprocal Rank  ms = avg latency
======================================================================
```

### Implementation

- **Isolation**: Uses temporary database, no pollution of production data
- **Clean fixtures**: All test data bundled in `fixtures.py`
- **No external deps**: Self-contained, runs immediately
- **Fast**: Completes in ~30 seconds with vector search

### Files

- `fixtures.py`: 35 memories + 25 labeled queries
- `eval_suite.py`: Benchmark runner, metrics, report formatting
- `run.py`: CLI entry point

---

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
