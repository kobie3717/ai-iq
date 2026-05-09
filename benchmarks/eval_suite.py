"""
Benchmark suite for AI-IQ memory retrieval.

Metrics:
  Recall@k  — fraction of queries where relevant memory appears in top-k results
  MRR       — Mean Reciprocal Rank (1/rank of first relevant hit, 0 if not found)
  Latency   — mean retrieval time in ms

Compares modes: keyword, semantic, hybrid (baseline), hybrid (with PPR+causal).
"""

import sys
import os
import time
import sqlite3
import tempfile
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool.database import get_db, init_db
from memory_tool.memory_ops import search_memories, add_memory
from memory_tool.embedding import embed_and_store, has_vec_support
from benchmarks.fixtures import MEMORIES, QUERIES


def setup_benchmark_db() -> Tuple[List[int], str]:
    """Create a temp DB seeded with benchmark memories. Returns (mem_ids, db_path)."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, 'benchmark.db')

    # Point memory_tool at the temp DB
    os.environ['AIIQ_DB_PATH'] = db_path

    # Monkey-patch database module to use temp DB
    import memory_tool.database as db_mod
    import memory_tool.config as config_mod

    # Store original path
    original_path = config_mod.DB_PATH

    # Update paths
    config_mod.DB_PATH = Path(db_path)
    db_mod.DB_PATH = Path(db_path)

    # Initialize fresh DB
    init_db()

    print(f"Seeding {len(MEMORIES)} memories...", end=' ', flush=True)
    mem_ids = []
    for m in MEMORIES:
        # Use add_memory with category as first parameter
        mid = add_memory(
            category=m.get('category', 'learning'),
            content=m['content'],
            tags=m.get('tags', ''),
            project=m.get('project'),
            skip_dedup=True,  # Skip dedup for clean benchmark data
        )
        mem_ids.append(mid)

    # Embed all memories if vector search is available
    if has_vec_support():
        conn = get_db()
        for mid in mem_ids:
            row = conn.execute("SELECT content FROM memories WHERE id = ?", (mid,)).fetchone()
            if row:
                embed_and_store(conn, mid, row['content'])
        conn.commit()
        conn.close()

    print("done")
    return mem_ids, db_path


def recall_at_k(results: List[Dict], relevant_indices: List[int], mem_ids: List[int], k: int) -> float:
    """1.0 if any relevant memory appears in top-k, else 0.0"""
    relevant_ids = {mem_ids[i] for i in relevant_indices if i < len(mem_ids)}
    top_k_ids = {r['id'] for r in results[:k]}
    return 1.0 if relevant_ids & top_k_ids else 0.0


def mrr(results: List[Dict], relevant_indices: List[int], mem_ids: List[int]) -> float:
    """Mean reciprocal rank: 1/rank of first relevant result (0 if not found)."""
    relevant_ids = {mem_ids[i] for i in relevant_indices if i < len(mem_ids)}
    for rank, r in enumerate(results, 1):
        if r['id'] in relevant_ids:
            return 1.0 / rank
    return 0.0


def run_mode(mode: str, queries: List[Dict], mem_ids: List[int]) -> Dict[str, Any]:
    """Run all queries in a given search mode, return metrics."""
    recalls_1 = []
    recalls_3 = []
    recalls_5 = []
    mrrs = []
    latencies = []

    for q in queries:
        t0 = time.perf_counter()
        try:
            rows, _, _ = search_memories(q['query'], mode=mode)
            # Convert rows to dicts
            results = [dict(r) for r in rows] if rows else []
        except Exception as e:
            # If search fails, treat as empty results
            results = []
        elapsed = (time.perf_counter() - t0) * 1000

        rel = q['relevant']

        recalls_1.append(recall_at_k(results, rel, mem_ids, 1))
        recalls_3.append(recall_at_k(results, rel, mem_ids, 3))
        recalls_5.append(recall_at_k(results, rel, mem_ids, 5))
        mrrs.append(mrr(results, rel, mem_ids))
        latencies.append(elapsed)

    n = len(queries)
    return {
        'recall@1': sum(recalls_1) / n if n > 0 else 0.0,
        'recall@3': sum(recalls_3) / n if n > 0 else 0.0,
        'recall@5': sum(recalls_5) / n if n > 0 else 0.0,
        'mrr': sum(mrrs) / n if n > 0 else 0.0,
        'latency_ms': sum(latencies) / n if n > 0 else 0.0,
        'n_queries': n,
    }


def run_benchmark(verbose: bool = True) -> Dict[str, Any]:
    """Run full benchmark. Returns results dict."""
    mem_ids, db_path = setup_benchmark_db()

    modes = ['keyword', 'semantic', 'hybrid']
    all_results = {}
    query_splits = {
        'all': QUERIES,
        'keyword': [q for q in QUERIES if q['type'] == 'keyword'],
        'semantic': [q for q in QUERIES if q['type'] == 'semantic'],
        'causal': [q for q in QUERIES if q['type'] == 'causal'],
    }

    for mode in modes:
        all_results[mode] = {}
        for split_name, split_queries in query_splits.items():
            if not split_queries:
                continue
            if verbose:
                print(f"Running {mode} mode on {split_name} queries ({len(split_queries)} queries)...", end=' ', flush=True)
            all_results[mode][split_name] = run_mode(mode, split_queries, mem_ids)
            if verbose:
                print("done")

    if verbose:
        _print_report(all_results)

    return all_results


def _print_report(results: Dict[str, Any]) -> None:
    """Print formatted benchmark report."""
    print("\n" + "=" * 70)
    print("AI-IQ RETRIEVAL BENCHMARK")
    print("=" * 70)

    splits = ['all', 'keyword', 'semantic', 'causal']
    modes = ['keyword', 'semantic', 'hybrid']

    for split in splits:
        print(f"\n── Query type: {split.upper()} ──")
        print(f"{'Mode':<12} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'MRR':>6} {'ms':>7}")
        print("-" * 45)
        for mode in modes:
            m = results.get(mode, {}).get(split)
            if not m:
                continue
            print(
                f"{mode:<12} "
                f"{m['recall@1']:>5.1%} "
                f"{m['recall@3']:>5.1%} "
                f"{m['recall@5']:>5.1%} "
                f"{m['mrr']:>5.3f} "
                f"{m['latency_ms']:>6.1f}ms"
            )

    print("\n" + "=" * 70)
    print("Legend: R@k = Recall@k  MRR = Mean Reciprocal Rank  ms = avg latency")
    print("=" * 70 + "\n")
