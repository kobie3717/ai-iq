#!/usr/bin/env python3
"""
LongMemEval benchmark for AI-IQ memory system.

Tests AI-IQ's hybrid search against the LongMemEval benchmark to measure
retrieval accuracy on long conversation histories.

Benchmark: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
Reference: MemPalace achieves 96.6% R@5 on this benchmark
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Set isolated DB path BEFORE importing memory_tool modules
DB_PATH = os.environ.get('MEMORY_DB', '/tmp/longmemeval-test.db')
os.environ['MEMORY_DB'] = DB_PATH

# Suppress AI-IQ warnings during benchmark
logging.getLogger('memory_tool').setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)

# Now safe to import AI-IQ modules
from memory_tool.memory_ops import add_memory, search_memories
from memory_tool.database import init_db, get_db


def download_dataset(variant: str = 's') -> Path:
    """Download LongMemEval dataset if not cached.

    Args:
        variant: Dataset variant ('s' for small [500 questions], 'm' for medium, 'oracle' for oracle baseline)

    Returns:
        Path to downloaded JSON file
    """
    cache_dir = Path('/tmp/longmemeval')
    cache_dir.mkdir(exist_ok=True)

    # Map variant to filename
    filename_map = {
        's': 'longmemeval_s_cleaned.json',
        'm': 'longmemeval_m_cleaned.json',
        'oracle': 'longmemeval_oracle.json'
    }

    if variant not in filename_map:
        print(f"Error: Unknown variant '{variant}'. Use 's', 'm', or 'oracle'")
        sys.exit(1)

    filename = filename_map[variant]
    dataset_file = cache_dir / filename

    if dataset_file.exists():
        print(f"Using cached dataset: {dataset_file}")
        return dataset_file

    print(f"Downloading LongMemEval-{variant.upper()} dataset...")
    url = f"https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/{filename}"

    # Use wget for reliable download
    import subprocess
    result = subprocess.run(
        ['wget', '-O', str(dataset_file), url],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error downloading dataset:")
        print(result.stderr)
        print(f"URL: {url}")
        sys.exit(1)

    print(f"Downloaded to: {dataset_file}")
    return dataset_file


def load_dataset(filepath: Path) -> List[Dict[str, Any]]:
    """Load LongMemEval dataset from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def ingest_question(question: Dict[str, Any], question_idx: int) -> Tuple[str, List[str]]:
    """Ingest all haystack sessions for a single question.

    Args:
        question: Question dict with 'haystack_sessions', 'question', 'answer_session_ids'
        question_idx: Question index for unique room ID

    Returns:
        Tuple of (question_text, gold_session_ids)
    """
    room_id = f"q{question_idx}"
    haystack_sessions = question.get('haystack_sessions', [])
    haystack_session_ids = question.get('haystack_session_ids', [])
    question_text = question.get('question', '')
    answer_session_ids = question.get('answer_session_ids', [])

    # Ingest each session as a memory (parallel arrays)
    for session_id, messages in zip(haystack_session_ids, haystack_sessions):
        # Concatenate all messages in the session
        content_parts = []
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            content_parts.append(f"{role}: {content}")

        session_content = "\n".join(content_parts)

        # Store as memory — prefix content with session_id for reliable retrieval
        # Use project field to store clean session_id (avoids auto-tag pollution)
        add_memory(
            category='learning',
            content=f"SESSION_ID:{session_id}\n{session_content}",
            tags=f"benchmark,{session_id}",
            project=session_id,
            wing='longmemeval',
            room=room_id,
            skip_dedup=True  # Don't deduplicate benchmark data
        )

    return question_text, answer_session_ids


def query_question(question_text: str, room_id: str, top_k: int = 5) -> List[str]:
    """Query for a question and return top-K session IDs.

    Args:
        question_text: The question to search for
        room_id: Room ID to filter results
        top_k: Number of results to retrieve

    Returns:
        List of session IDs (from tags) in top-K results
    """
    results, search_id, temporal_range = search_memories(
        query=question_text,
        mode='hybrid',
        wing='longmemeval',
        room=room_id
    )

    # Extract session IDs from project field (clean, no auto-tag pollution)
    session_ids = []
    for row in results[:top_k]:
        project = row['project'] if row['project'] else ''
        if project:
            session_ids.append(project)

    return session_ids


def compute_r_at_k(retrieved_ids: List[str], gold_ids: List[str]) -> bool:
    """Check if any gold ID is in retrieved IDs (R@K metric).

    Args:
        retrieved_ids: List of retrieved session IDs (from project field)
        gold_ids: List of gold session IDs

    Returns:
        True if any gold ID found in retrieved IDs
    """
    for gold_id in gold_ids:
        if gold_id in retrieved_ids:
            return True
    return False


def run_benchmark(dataset_path: Path, limit: int = None, top_k: int = 5) -> Dict[str, Any]:
    """Run full LongMemEval benchmark.

    Args:
        dataset_path: Path to dataset JSON
        limit: Limit number of questions (for testing)
        top_k: Number of results to retrieve (default 5 for R@5)

    Returns:
        Dict with results: {
            'total': int,
            'correct': int,
            'r_at_k': float,
            'questions': List[Dict]  # Per-question results
        }
    """
    # Initialize fresh database
    print(f"Initializing database at: {DB_PATH}")
    init_db()

    # Load dataset
    print(f"Loading dataset from: {dataset_path}")
    questions = load_dataset(dataset_path)

    if limit:
        questions = questions[:limit]
        print(f"Limited to {limit} questions")

    print(f"Total questions: {len(questions)}")
    print(f"Starting benchmark (R@{top_k})...")
    print(f"Ingesting {sum(len(q.get('haystack_sessions', [])) for q in questions)} total sessions...")
    print()

    correct_count = 0
    results = []

    for idx, question in enumerate(questions):
        # Ingest sessions for this question
        print(f"[{idx+1}/{len(questions)}] Ingesting question {idx}...", end=' ', flush=True)
        question_text, gold_session_ids = ingest_question(question, idx)
        room_id = f"q{idx}"
        print(f"Querying...", end=' ', flush=True)

        # Query and retrieve top-K
        retrieved_ids = query_question(question_text, room_id, top_k=top_k)

        # Check if correct
        is_correct = compute_r_at_k(retrieved_ids, gold_session_ids)
        if is_correct:
            correct_count += 1

        # Store per-question result
        results.append({
            'question_idx': idx,
            'question': question_text[:100] + '...' if len(question_text) > 100 else question_text,
            'gold_ids': gold_session_ids,
            'retrieved_ids': retrieved_ids,
            'correct': is_correct
        })

        # Print result
        result_symbol = "✓" if is_correct else "✗"
        current_acc = (correct_count / (idx + 1)) * 100
        print(f"{result_symbol} R@{top_k}={current_acc:.1f}%")

        # Summary progress update
        if (idx + 1) % 10 == 0:
            print(f"\n--- Progress: {idx + 1}/{len(questions)} completed ---\n")

    # Final results
    total = len(questions)
    r_at_k = (correct_count / total) * 100 if total > 0 else 0.0

    return {
        'total': total,
        'correct': correct_count,
        'r_at_k': r_at_k,
        'top_k': top_k,
        'questions': results
    }


def print_results(results: Dict[str, Any]):
    """Print benchmark results."""
    print("\n" + "=" * 70)
    print("LONGMEMEVAL BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Total Questions: {results['total']}")
    print(f"Correct: {results['correct']}")
    print(f"R@{results['top_k']}: {results['r_at_k']:.2f}%")
    print("-" * 70)
    print(f"AI-IQ:      {results['r_at_k']:.1f}%")
    print(f"MemPalace:  96.6%  (reference)")
    print(f"Difference: {results['r_at_k'] - 96.6:+.1f}%")
    print("=" * 70)

    # Show some examples
    if results['questions']:
        print("\nSample Results (first 5):")
        for q in results['questions'][:5]:
            status = "✓" if q['correct'] else "✗"
            print(f"  {status} Q{q['question_idx']}: {q['question']}")
            print(f"     Gold: {q['gold_ids']}")
            print(f"     Retrieved: {q['retrieved_ids'][:3]}...")  # Show first 3
            print()


def save_results(results: Dict[str, Any], output_path: Path):
    """Save detailed results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {output_path}")


def cleanup_database():
    """Remove test database."""
    db_path = Path(DB_PATH)
    if db_path.exists():
        db_path.unlink()
        print(f"Removed test database: {db_path}")
        # Also remove WAL files
        for suffix in ['-wal', '-shm']:
            wal_file = Path(str(db_path) + suffix)
            if wal_file.exists():
                wal_file.unlink()


def main():
    parser = argparse.ArgumentParser(
        description='Run LongMemEval benchmark on AI-IQ memory system'
    )
    parser.add_argument(
        '--variant',
        choices=['s', 'm', 'oracle'],
        default='s',
        help='Dataset variant: s(mall) [500q], m(edium), oracle (default: s)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of questions (for testing)'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of results to retrieve (default: 5 for R@5)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('/tmp/longmemeval-results.json'),
        help='Output path for detailed results JSON (default: /tmp/longmemeval-results.json)'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove test database after run'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("AI-IQ LONGMEMEVAL BENCHMARK")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Variant: {args.variant.upper()}")
    if args.limit:
        print(f"Limit: {args.limit} questions (TEST MODE)")
    print()

    try:
        # Download dataset
        dataset_path = download_dataset(args.variant)

        # Run benchmark
        start_time = datetime.now()
        results = run_benchmark(
            dataset_path=dataset_path,
            limit=args.limit,
            top_k=args.top_k
        )
        end_time = datetime.now()

        # Print results
        print_results(results)

        # Save detailed results
        save_results(results, args.output)

        # Print timing
        duration = (end_time - start_time).total_seconds()
        print(f"\nTotal time: {duration:.1f}s ({duration/results['total']:.2f}s per question)")

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup if requested
        if args.cleanup:
            cleanup_database()


if __name__ == '__main__':
    main()
